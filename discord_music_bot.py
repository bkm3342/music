import discord
from discord.ext import commands
import yt_dlp
import spotipy
import re
import asyncio
import os
import logging
import time
from spotipy.oauth2 import SpotifyClientCredentials

# Load opus for voice support
try:
    discord.opus.load_opus('/nix/store/2m0ngng1iy80h65052chw7mn18qbgq0w-libopus-1.5.2/lib/libopus.so.0')
except:
    try:
        discord.opus.load_opus('/nix/store/2m0ngng1iy80h65052chw7mn18qbgq0w-libopus-1.5.2/lib/libopus.so')
    except:
        try:
            discord.opus.load_opus('libopus.so.0')
        except:
            try:
                discord.opus.load_opus('libopus.so')
            except:
                pass

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Bot Configuration ----
DISCORD_BOT_TOKEN = "MTM4MzY3ODk2MjgzMTU4OTUwOQ.G1uWjY.ctY6kbpI7HQeeec9QIq0NdMGS0LF_vQ_UlDhFg"
SPOTIFY_CLIENT_ID = "56a295f2e2d0424588992d92275cd1c8"  
SPOTIFY_CLIENT_SECRET = "eba3e96a03334f7a832ae5f06ceb48d2"

SPOTIFY_ENABLED = True

# ---- Spotify Setup ----
if SPOTIFY_ENABLED:
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        ))
        logger.info("Spotify client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Spotify client: {e}")
        SPOTIFY_ENABLED = False

# ---- Discord Intents ----
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='/', intents=intents)

# ---- YouTube & FFmpeg Config for high quality audio ----
FFMPEG_PATH = 'ffmpeg'

# Enhanced audio quality settings
ytdl_format_options = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'default_search': 'ytsearch1',
    'extractaudio': True,
    'audioformat': 'mp3',
    'audioquality': '0',  # Best quality
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'logtostderr': False,
    'ignoreerrors': False,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'prefer_ffmpeg': True
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# Enhanced FFmpeg options for better audio quality with dynamic volume and seeking
def get_ffmpeg_options(volume=0.5, seek_time=0):
    # Only use seek if it's greater than 1 second to avoid FFmpeg errors with very small values
    seek_option = f'-ss {int(seek_time)}' if seek_time >= 1 else ''
    return {
        'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 50M -analyzeduration 50M {seek_option}',
        'options': f'-vn -filter:a "volume={volume}" -ar 48000 -ac 2 -b:a 192k'
    }

# Global storage - separated by guild for multi-server support
current_guild_queues = {}
current_song_info = {}
guild_voice_clients = {}
song_start_times = {}  # Track when songs started playing
current_audio_urls = {}  # Track current audio URLs for volume changes
played_songs_history = {}  # Track played songs to avoid repetition
volume_messages = {}  # Track volume messages for editing
paused_guilds = set()  # Track paused guilds to prevent auto-play

async def generate_smart_autoplay_query(current_song):
    """Generate intelligent search queries for autoplay to avoid repeating songs"""
    import random
    
    # Extract key words from current song title
    title_lower = current_song.lower()
    
    # Define different search strategies based on song content
    search_strategies = []
    
    # Strategy 1: Genre-based search
    if any(genre in title_lower for genre in ['punjabi', 'hindi', 'bollywood', 'rap', 'pop', 'rock']):
        if 'punjabi' in title_lower:
            search_strategies.extend([
                "new punjabi songs 2024",
                "latest punjabi hits",
                "punjabi music trending",
                "sidhu moose wala songs",
                "karan aujla new song"
            ])
        elif 'hindi' in title_lower or 'bollywood' in title_lower:
            search_strategies.extend([
                "latest bollywood songs 2024",
                "new hindi songs",
                "trending bollywood music",
                "arijit singh songs",
                "raghav chaitanya songs"
            ])
    
    # Strategy 2: Mood-based search
    if any(mood in title_lower for mood in ['sad', 'love', 'party', 'romantic', 'dance']):
        if 'love' in title_lower or 'romantic' in title_lower:
            search_strategies.extend([
                "romantic songs 2024",
                "love songs hindi",
                "romantic bollywood songs"
            ])
        elif 'dance' in title_lower or 'party' in title_lower:
            search_strategies.extend([
                "dance songs 2024",
                "party songs hindi",
                "club music trending"
            ])
    
    # Strategy 3: Artist-based search (extract potential artist names)
    words = current_song.split()
    potential_artists = []
    for word in words:
        if len(word) > 3 and word.isupper():
            potential_artists.append(word)
    
    if potential_artists:
        for artist in potential_artists[:2]:  # Use first 2 potential artists
            search_strategies.append(f"{artist} new songs")
            search_strategies.append(f"{artist} latest music")
    
    # Strategy 4: General trending searches
    search_strategies.extend([
        "trending songs 2024",
        "viral songs india",
        "latest music hits",
        "new songs this week",
        "popular songs 2024",
        "top charts india",
        "youtube trending music"
    ])
    
    # Select a random strategy to ensure variety
    if search_strategies:
        return random.choice(search_strategies)
    else:
        # Fallback to generic search
        return "trending songs 2024"

class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.is_auto_play = True
        self.loop_current = False
        self.loop_queue = False
        self.volume = 0.5  # Default volume (50%)
        
    def add(self, item):
        self.queue.append(item)
        
    def next(self):
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        return None
        
    def clear(self):
        self.queue.clear()
        self.current = None
        
    def is_empty(self):
        return len(self.queue) == 0
        
    def size(self):
        return len(self.queue)
        
    def toggle_auto_play(self):
        self.is_auto_play = not self.is_auto_play
        return self.is_auto_play
    
    def increase_volume(self):
        self.volume = min(1.0, self.volume + 0.1)
        return self.volume
    
    def decrease_volume(self):
        self.volume = max(0.1, self.volume - 0.1)
        return self.volume
    
    def get_volume_percentage(self):
        return int(self.volume * 100)

def get_guild_queue(guild_id):
    if guild_id not in current_guild_queues:
        current_guild_queues[guild_id] = MusicQueue()
    return current_guild_queues[guild_id]

# Enhanced Music Player Dashboard
class MusicDashboardView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        
    @discord.ui.button(label="⏸️ Pause", style=discord.ButtonStyle.secondary, row=0)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                paused_guilds.add(interaction.guild.id)  # Track paused state
                await interaction.response.send_message("⏸️ Music paused")
            else:
                await interaction.response.send_message("❌ Nothing is playing")
        except Exception as e:
            logger.error(f"Pause button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred")
            
    @discord.ui.button(label="▶️ Resume", style=discord.ButtonStyle.success, row=0)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                paused_guilds.discard(interaction.guild.id)  # Remove from paused state
                await interaction.response.send_message("▶️ Music resumed")
            else:
                await interaction.response.send_message("❌ Nothing is paused")
        except Exception as e:
            logger.error(f"Resume button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred")
            
    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary, row=0)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            voice_client = interaction.guild.voice_client
            guild_queue = get_guild_queue(self.guild_id)
            
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                
                # Smart skip: Always check queue first, then auto-play similar music
                if not guild_queue.is_empty():
                    # Songs in queue - play next from queue
                    next_song = guild_queue.next()
                    await interaction.response.send_message(f"⏭️ Playing next from queue: **{next_song}**", ephemeral=True)
                    
                    # Immediately play next song from queue
                    try:
                        if SPOTIFY_ENABLED and 'spotify.com/track/' in next_song:
                            await self.play_next_spotify_track(interaction, next_song)
                        elif SPOTIFY_ENABLED and 'spotify.com/playlist/' in next_song:
                            await self.play_next_spotify_playlist(interaction, next_song)  
                        elif 'youtube.com' in next_song or 'youtu.be' in next_song:
                            await self.play_next_youtube(interaction, next_song)
                        else:
                            await self.play_next_youtube_search(interaction, next_song)
                    except Exception as play_error:
                        logger.error(f"Error playing next song: {play_error}")
                        await interaction.followup.send("❌ Error playing next song", ephemeral=True)
                else:
                    # Queue is empty - automatically find and play similar music
                    current_song = current_song_info.get(self.guild_id)
                    if current_song:
                        await interaction.response.send_message("⏭️ Queue empty - Finding similar music automatically...", ephemeral=True)
                        similar_query = await generate_smart_autoplay_query(current_song)
                        try:
                            await self.play_next_youtube_search(interaction, similar_query)
                            await interaction.followup.send(f"🎵 Now playing similar: **{similar_query}**", ephemeral=True)
                        except Exception as play_error:
                            logger.error(f"Error in autoplay: {play_error}")
                            await interaction.followup.send("❌ Could not find similar music", ephemeral=True)
                    else:
                        await interaction.response.send_message("⏭️ Skipped - No previous song to find similar music", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing is playing", ephemeral=True)
        except Exception as e:
            logger.error(f"Skip button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)
    
    async def play_next_youtube_search(self, interaction, query):
        """Play next song from YouTube search immediately"""
        try:
            search_query = f"{query} song" if not any(keyword in query.lower() for keyword in ['song', 'music', 'audio']) else query
            info = ytdl.extract_info(f"ytsearch:{search_query}", download=False)
            
            if info and info.get('entries'):
                video_info = info['entries'][0]
                audio_url = self.get_best_audio_url(video_info)
                if audio_url:
                    await self.start_audio_playback(interaction, audio_url, video_info.get('title', 'Unknown'))
        except Exception as e:
            logger.error(f"Error in play_next_youtube_search: {e}")
    
    async def play_next_youtube(self, interaction, url):
        """Play next song from YouTube URL immediately"""
        try:
            info = ytdl.extract_info(url, download=False)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]
            
            if info:
                audio_url = self.get_best_audio_url(info)
                if audio_url:
                    await self.start_audio_playback(interaction, audio_url, info.get('title', 'Unknown'))
        except Exception as e:
            logger.error(f"Error in play_next_youtube: {e}")
    
    async def play_next_spotify_track(self, interaction, url):
        """Play next Spotify track immediately"""
        try:
            track_id = extract_spotify_track_id(url)
            if track_id and SPOTIFY_ENABLED:
                track = sp.track(track_id)
                query = f"{track['name']} {track['artists'][0]['name']}"
                await self.play_next_youtube_search(interaction, query)
        except Exception as e:
            logger.error(f"Error in play_next_spotify_track: {e}")
    
    async def play_next_spotify_playlist(self, interaction, url):
        """Play first track from Spotify playlist immediately"""
        try:
            playlist_id = extract_spotify_playlist_id(url)
            if playlist_id and SPOTIFY_ENABLED:
                playlist = sp.playlist(playlist_id)
                tracks = playlist['tracks']['items']
                if tracks and tracks[0]['track']:
                    track = tracks[0]['track']
                    query = f"{track['name']} {track['artists'][0]['name']}"
                    await self.play_next_youtube_search(interaction, query)
        except Exception as e:
            logger.error(f"Error in play_next_spotify_playlist: {e}")
    
    def get_best_audio_url(self, video_info):
        """Get best quality audio URL from video info"""
        formats = video_info.get('formats', [])
        
        # Try M4A first (best quality)
        for fmt in formats:
            if (fmt.get('acodec', 'none') != 'none' and 
                fmt.get('vcodec', 'none') == 'none' and 
                fmt.get('ext') == 'm4a'):
                return fmt.get('url')
        
        # Try any audio-only format
        for fmt in formats:
            if (fmt.get('acodec', 'none') != 'none' and 
                fmt.get('vcodec', 'none') == 'none'):
                return fmt.get('url')
        
        # Fallback to main URL
        return video_info.get('url')
    
    async def start_audio_playback(self, interaction, audio_url, title):
        """Start audio playback with current volume settings"""
        try:
            guild_queue = get_guild_queue(interaction.guild.id)
            voice_client = interaction.guild.voice_client
            
            if voice_client and audio_url:
                # Use PCMVolumeTransformer for real-time volume control
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(
                        audio_url,
                        executable=FFMPEG_PATH,
                        **get_ffmpeg_options()
                    ),
                    volume=guild_queue.volume
                )
                
                voice_client.play(source, after=lambda e: asyncio.create_task(self.on_song_finished(interaction.guild.id)) if e is None else None)
                current_song_info[interaction.guild.id] = title
                # Track when song started and cache audio URL
                song_start_times[interaction.guild.id] = time.time()
                current_audio_urls[interaction.guild.id] = audio_url
                logger.info(f"Now playing: {title} in guild: {interaction.guild.name}")
        except Exception as e:
            logger.error(f"Error in start_audio_playback: {e}")

    async def on_song_finished(self, guild_id):
        """Handle when a song finishes playing"""
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                return
                
            guild_queue = get_guild_queue(guild_id)
            voice_client = guild.voice_client
            
            if voice_client and guild_queue.is_auto_play:
                if not guild_queue.is_empty():
                    # Play next song from queue
                    next_song = guild_queue.next()
                    current_song_info[guild_id] = next_song
                    logger.info(f"Auto-playing next from queue: {next_song}")
                    
                    # Play next song based on type
                    if SPOTIFY_ENABLED and 'spotify.com/track/' in next_song:
                        await self.play_next_spotify_track_auto(guild, next_song)
                    elif SPOTIFY_ENABLED and 'spotify.com/playlist/' in next_song:
                        await self.play_next_spotify_playlist_auto(guild, next_song)  
                    elif 'youtube.com' in next_song or 'youtu.be' in next_song:
                        await self.play_next_youtube_auto(guild, next_song)
                    else:
                        await self.play_next_youtube_search_auto(guild, next_song)
                else:
                    # Generate autoplay suggestion
                    current_song = current_song_info.get(guild_id)
                    if current_song:
                        similar_query = await generate_smart_autoplay_query(current_song)
                        logger.info(f"Auto-playing similar: {similar_query}")
                        await self.play_next_youtube_search_auto(guild, similar_query)
        except Exception as e:
            logger.error(f"Error in on_song_finished: {e}")

    async def play_next_youtube_search_auto(self, guild, query):
        """Auto-play next song from YouTube search"""
        try:
            search_query = f"{query} song" if not any(keyword in query.lower() for keyword in ['song', 'music', 'audio']) else query
            info = ytdl.extract_info(f"ytsearch:{search_query}", download=False)
            
            if info and info.get('entries'):
                video_info = info['entries'][0]
                audio_url = self.get_best_audio_url(video_info)
                title = video_info.get('title', 'Unknown')
                
                if audio_url:
                    guild_queue = get_guild_queue(guild.id)
                    source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio(
                            audio_url,
                            executable=FFMPEG_PATH,
                            **get_ffmpeg_options()
                        ),
                        volume=guild_queue.volume
                    )
                    
                    voice_client = guild.voice_client
                    if voice_client:
                        voice_client.play(source, after=lambda e: asyncio.create_task(self.on_song_finished(guild.id)) if e is None else None)
                        current_song_info[guild.id] = title
                        song_start_times[guild.id] = time.time()
                        current_audio_urls[guild.id] = audio_url
        except Exception as e:
            logger.error(f"Error in play_next_youtube_search_auto: {e}")

    async def play_next_youtube_auto(self, guild, url):
        """Auto-play next song from YouTube URL"""
        try:
            info = ytdl.extract_info(url, download=False)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]
            
            if info:
                audio_url = self.get_best_audio_url(info)
                title = info.get('title', 'Unknown')
                
                if audio_url:
                    guild_queue = get_guild_queue(guild.id)
                    source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio(
                            audio_url,
                            executable=FFMPEG_PATH,
                            **get_ffmpeg_options()
                        ),
                        volume=guild_queue.volume
                    )
                    
                    voice_client = guild.voice_client
                    if voice_client:
                        voice_client.play(source, after=lambda e: asyncio.create_task(self.on_song_finished(guild.id)) if e is None else None)
                        current_song_info[guild.id] = title
                        song_start_times[guild.id] = time.time()
                        current_audio_urls[guild.id] = audio_url
        except Exception as e:
            logger.error(f"Error in play_next_youtube_auto: {e}")

    async def play_next_spotify_track_auto(self, guild, url):
        """Auto-play next Spotify track"""
        try:
            track_id = extract_spotify_track_id(url)
            if track_id and SPOTIFY_ENABLED:
                track = sp.track(track_id)
                query = f"{track['name']} {track['artists'][0]['name']}"
                await self.play_next_youtube_search_auto(guild, query)
        except Exception as e:
            logger.error(f"Error in play_next_spotify_track_auto: {e}")

    async def play_next_spotify_playlist_auto(self, guild, url):
        """Auto-play first track from Spotify playlist"""
        try:
            playlist_id = extract_spotify_playlist_id(url)
            if playlist_id and SPOTIFY_ENABLED:
                playlist = sp.playlist(playlist_id)
                tracks = playlist['tracks']['items']
                if tracks and tracks[0]['track']:
                    track = tracks[0]['track']
                    query = f"{track['name']} {track['artists'][0]['name']}"
                    await self.play_next_youtube_search_auto(guild, query)
        except Exception as e:
            logger.error(f"Error in play_next_spotify_playlist_auto: {e}")
            
    @discord.ui.button(label="🔄 Auto-Play: ON", style=discord.ButtonStyle.success, row=1)
    async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild_queue = get_guild_queue(self.guild_id)
            is_on = guild_queue.toggle_auto_play()
            
            if is_on:
                button.label = "🔄 Auto-Play: ON"
                button.style = discord.ButtonStyle.success
            else:
                button.label = "🔄 Auto-Play: OFF"
                button.style = discord.ButtonStyle.danger
                
            await interaction.response.edit_message(view=self)
        except Exception as e:
            logger.error(f"Auto-play button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)
            
    @discord.ui.button(label="📜 Queue", style=discord.ButtonStyle.secondary, row=1)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild_queue = get_guild_queue(self.guild_id)
            
            if guild_queue.is_empty():
                await interaction.response.send_message("❌ Queue is empty", ephemeral=True)
                return
            
            embed = discord.Embed(title="🎵 Current Queue", color=0x00ff00)
            
            queue_list = []
            for i, song in enumerate(guild_queue.queue[:10]):
                queue_list.append(f"{i + 1}. {song}")
            
            if len(guild_queue.queue) > 10:
                queue_list.append(f"... and {len(guild_queue.queue) - 10} more songs")
            
            embed.description = "\n".join(queue_list) if queue_list else "Queue is empty"
            embed.add_field(name="Total Songs", value=str(guild_queue.size()), inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Queue button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)
        
    @discord.ui.button(label="🔊+", style=discord.ButtonStyle.secondary, row=1)
    async def volume_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild_queue = get_guild_queue(self.guild_id)
            old_volume = guild_queue.volume
            new_volume = guild_queue.increase_volume()
            
            # Check if there's an existing volume message to edit
            if interaction.guild.id in volume_messages:
                try:
                    await volume_messages[interaction.guild.id].edit(content=f"🔊 Volume: {guild_queue.get_volume_percentage()}%")
                    await interaction.response.send_message("Volume updated", ephemeral=True)
                except:
                    # If editing fails, send new message and store it
                    await interaction.response.send_message(f"🔊 Volume: {guild_queue.get_volume_percentage()}%")
                    volume_messages[interaction.guild.id] = await interaction.original_response()
            else:
                # Send new message and store it for future edits
                await interaction.response.send_message(f"🔊 Volume: {guild_queue.get_volume_percentage()}%")
                volume_messages[interaction.guild.id] = await interaction.original_response()
            
            # Apply volume change without restarting the song
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.source and hasattr(voice_client.source, 'volume'):
                # Apply volume instantly using PCMVolumeTransformer
                voice_client.source.volume = new_volume
                logger.info(f"Volume instantly changed to {guild_queue.get_volume_percentage()}%")
            
        except Exception as e:
            logger.error(f"Volume up error: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error occurred", ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label="🔉-", style=discord.ButtonStyle.secondary, row=1)
    async def volume_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild_queue = get_guild_queue(self.guild_id)
            old_volume = guild_queue.volume
            new_volume = guild_queue.decrease_volume()
            
            # Check if there's an existing volume message to edit
            if interaction.guild.id in volume_messages:
                try:
                    await volume_messages[interaction.guild.id].edit(content=f"🔉 Volume: {guild_queue.get_volume_percentage()}%")
                    await interaction.response.send_message("Volume updated", ephemeral=True)
                except:
                    # If editing fails, send new message and store it
                    await interaction.response.send_message(f"🔉 Volume: {guild_queue.get_volume_percentage()}%")
                    volume_messages[interaction.guild.id] = await interaction.original_response()
            else:
                # Send new message and store it for future edits
                await interaction.response.send_message(f"🔉 Volume: {guild_queue.get_volume_percentage()}%")
                volume_messages[interaction.guild.id] = await interaction.original_response()
            
            # Apply volume change without restarting the song
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.source and hasattr(voice_client.source, 'volume'):
                # Apply volume instantly using PCMVolumeTransformer
                voice_client.source.volume = new_volume
                logger.info(f"Volume instantly changed to {guild_queue.get_volume_percentage()}%")
            
        except Exception as e:
            logger.error(f"Volume down error: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error occurred", ephemeral=True)
            except:
                pass
    
    async def restart_audio_with_volume(self, interaction, title, volume):
        """Restart current audio with new volume quickly"""
        try:
            # Use a background task to avoid blocking the interaction
            asyncio.create_task(self._restart_audio_background(interaction.guild.id, title, volume))
        except Exception as e:
            logger.error(f"Error scheduling audio restart: {e}")
    
    async def _restart_audio_background(self, guild_id, title, volume, seek_time=0):
        """Background task to restart audio with new volume from specific time"""
        try:
            await asyncio.sleep(0.05)  # Minimal delay to ensure stop completed
            
            # Get voice client from guild
            guild = bot.get_guild(guild_id)
            if guild and guild.voice_client:
                voice_client = guild.voice_client
                
                # Use cached audio URL if available, otherwise search again
                audio_url = current_audio_urls.get(guild_id)
                if not audio_url:
                    search_query = f"{title} song"
                    info = ytdl.extract_info(f"ytsearch:{search_query}", download=False)
                    
                    if info and info.get('entries'):
                        video_info = info['entries'][0]
                        audio_url = self.get_best_audio_url(video_info)
                        current_audio_urls[guild_id] = audio_url
                
                if audio_url:
                    # Create new audio source with updated volume and seek time
                    source = discord.FFmpegPCMAudio(
                        audio_url,
                        executable=FFMPEG_PATH,
                        **get_ffmpeg_options(volume, seek_time)
                    )
                    
                    # Start playing with new volume from specified time
                    voice_client.play(source)
                    current_song_info[guild_id] = title
                    # Update start time to account for the seek
                    song_start_times[guild_id] = time.time() - seek_time
                    logger.info(f"Volume instantly changed to {int(volume*100)}% for: {title} (resumed from {int(seek_time)}s)")
        except Exception as e:
            logger.error(f"Error in background audio restart: {e}")
        
    @discord.ui.button(label="🗑️ Clear Queue", style=discord.ButtonStyle.danger, row=2)
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild_queue = get_guild_queue(self.guild_id)
            guild_queue.clear()
            await interaction.response.send_message("🗑️ Queue cleared", ephemeral=True)
        except Exception as e:
            logger.error(f"Clear button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)
        
    @discord.ui.button(label="🔇 Stop & Leave", style=discord.ButtonStyle.danger, row=2)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            voice_client = interaction.guild.voice_client
            if voice_client:
                if voice_client.is_playing():
                    voice_client.stop()
                await voice_client.disconnect()
                guild_queue = get_guild_queue(self.guild_id)
                guild_queue.clear()
                if self.guild_id in current_song_info:
                    del current_song_info[self.guild_id]
                await interaction.response.send_message("🔇 Stopped music and left voice channel", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Not connected to any voice channel", ephemeral=True)
        except Exception as e:
            logger.error(f"Stop button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} slash commands globally")
    except Exception as e:
        logger.error(f"❌ Failed to sync commands: {e}")
    
    logger.info(f'✅ Logged in as {bot.user.name}')
    logger.info(f'Bot is ready! Multi-server support enabled. Spotify: {SPOTIFY_ENABLED}')

@bot.tree.command(name='play', description="Play music by song name, YouTube URL, or Spotify URL")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    try:
        # Check if user is in voice channel
        if not interaction.user.voice:
            await interaction.followup.send("❌ You need to be in a voice channel to use this command.", ephemeral=True)
            return
        
        # Connect to voice channel if not already connected
        if not interaction.guild.voice_client:
            try:
                voice_client = await interaction.user.voice.channel.connect()
                guild_voice_clients[interaction.guild.id] = voice_client
                logger.info(f"Connected to voice channel: {interaction.user.voice.channel.name} in guild: {interaction.guild.name}")
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to connect to voice channel: {e}")
                return
        
        guild_queue = get_guild_queue(interaction.guild.id)
        
        # If something is already playing, add to queue
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            guild_queue.add(query)
            embed = discord.Embed(
                title="🔥 Added to Queue",
                description=f"**{query}**",
                color=0xff9500
            )
            embed.add_field(name="Position", value=f"{guild_queue.size()}", inline=True)
            embed.add_field(name="Queue Size", value=f"{guild_queue.size()} songs", inline=True)
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await start_playback(interaction, query)
    except Exception as e:
        logger.error(f"Play command error: {e}")
        await interaction.followup.send(f"❌ An error occurred: {e}")

async def start_playback(interaction, query):
    """Start playing a song and handle queue progression"""
    try:
        if SPOTIFY_ENABLED and 'spotify.com/track/' in query:
            await play_spotify_track(interaction, query)
        elif SPOTIFY_ENABLED and 'spotify.com/playlist/' in query:
            await play_spotify_playlist(interaction, query)
        elif 'youtube.com' in query or 'youtu.be' in query:
            await play_youtube(interaction, query)
        else:
            await play_youtube_search(interaction, query)
            
        # Wait for current song to finish, then play next in queue
        await wait_for_song_completion(interaction)
        
    except Exception as e:
        logger.error(f"Error in start_playback: {e}")
        await interaction.followup.send(f"❌ An error occurred: {e}")

async def start_playback_from_button(interaction, query):
    """Start playback triggered from button interaction (for skip functionality)"""
    try:
        if SPOTIFY_ENABLED and 'spotify.com/track/' in query:
            await play_spotify_track_simple(interaction, query)
        elif SPOTIFY_ENABLED and 'spotify.com/playlist/' in query:
            await play_spotify_playlist_simple(interaction, query)
        elif 'youtube.com' in query or 'youtu.be' in query:
            await play_youtube_simple(interaction, query)
        else:
            await play_youtube_search_simple(interaction, query)
    except Exception as e:
        logger.error(f"Error in start_playback_from_button: {e}")

async def wait_for_song_completion(interaction):
    """Wait for current song to complete and handle queue progression"""
    try:
        while interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            await asyncio.sleep(2)
        
        # Check if guild is paused - don't auto-play if paused
        if interaction.guild.id in paused_guilds:
            return
        
        guild_queue = get_guild_queue(interaction.guild.id)
        if guild_queue.is_auto_play:
            if not guild_queue.is_empty():
                # Play next song from queue
                next_song = guild_queue.next()
                await interaction.followup.send(f"🎵 Auto-Playing Next from Queue: {next_song}")
                await start_playback(interaction, next_song)
            else:
                # Queue is empty, find similar song automatically
                current_song = current_song_info.get(interaction.guild.id)
                if current_song:
                    # Add current song to history to avoid repetition
                    guild_id = interaction.guild.id
                    if guild_id not in played_songs_history:
                        played_songs_history[guild_id] = []
                    
                    # Keep only last 10 songs in history
                    played_songs_history[guild_id].append(current_song.lower())
                    if len(played_songs_history[guild_id]) > 10:
                        played_songs_history[guild_id].pop(0)
                    
                    # Generate a more intelligent search query for different songs
                    similar_query = await generate_smart_autoplay_query(current_song)
                    await interaction.followup.send(f"🎵 Auto-Playing: Finding similar music...")
                    await start_playback(interaction, similar_query)
    except Exception as e:
        logger.error(f"Wait for song completion error: {e}")

async def play_youtube_search_simple(interaction, query):
    """Simplified YouTube search for button interactions"""
    try:
        search_query = query
        if not any(keyword in query.lower() for keyword in ['song', 'music', 'audio', 'track', 'lyrics', 'official']):
            search_query = f"{query} song"
            
        info = ytdl.extract_info(f"ytsearch:{search_query}", download=False)
        if not info.get('entries'):
            return

        video_info = info['entries'][0]
        formats = video_info.get('formats', [])
        audio_url = None
        
        for fmt in formats:
            if (fmt.get('acodec', 'none') != 'none' and 
                fmt.get('vcodec', 'none') == 'none' and 
                fmt.get('ext') == 'm4a'):
                audio_url = fmt.get('url')
                break
                
        if not audio_url:
            for fmt in formats:
                if (fmt.get('acodec', 'none') != 'none' and 
                    fmt.get('vcodec', 'none') == 'none'):
                    audio_url = fmt.get('url')
                    break
                    
        if not audio_url:
            audio_url = video_info.get('url')
            
        if not audio_url:
            return
            
        title = video_info.get('title', 'Unknown Title')
        guild_queue = get_guild_queue(interaction.guild.id)
        
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                audio_url,
                executable=FFMPEG_PATH,
                **get_ffmpeg_options()
            ),
            volume=guild_queue.volume
        )

        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        voice_client.play(source)
        
        current_song_info[interaction.guild.id] = title
        # Track when song started and cache audio URL
        song_start_times[interaction.guild.id] = time.time()
        current_audio_urls[interaction.guild.id] = audio_url
        
    except Exception as e:
        logger.error(f"Simple YouTube search error: {e}")

async def play_youtube_simple(interaction, url):
    """Simplified YouTube play for button interactions"""
    try:
        info = ytdl.extract_info(url, download=False)
        
        if 'entries' in info:
            if not info['entries']:
                return
            info = info['entries'][0]
        
        if not info:
            return
        
        title = info.get('title', 'Unknown Title')
        formats = info.get('formats', [])
        audio_url = None
        
        for fmt in formats:
            if (fmt.get('acodec', 'none') != 'none' and 
                fmt.get('vcodec', 'none') == 'none' and 
                fmt.get('ext') == 'm4a'):
                audio_url = fmt.get('url')
                break
                
        if not audio_url:
            for fmt in formats:
                if (fmt.get('acodec', 'none') != 'none' and 
                    fmt.get('vcodec', 'none') == 'none'):
                    audio_url = fmt.get('url')
                    break
                    
        if not audio_url:
            audio_url = info.get('url')
            
        if not audio_url:
            return

        guild_queue = get_guild_queue(interaction.guild.id)
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                audio_url,
                executable=FFMPEG_PATH,
                **get_ffmpeg_options()
            ),
            volume=guild_queue.volume
        )

        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        voice_client.play(source)
        
        current_song_info[interaction.guild.id] = title
        # Track when song started and cache audio URL
        song_start_times[interaction.guild.id] = time.time()
        current_audio_urls[interaction.guild.id] = audio_url
        
    except Exception as e:
        logger.error(f"Simple YouTube play error: {e}")

async def play_spotify_track_simple(interaction, url):
    """Simplified Spotify track play for button interactions"""
    try:
        track_id = extract_spotify_track_id(url)
        if not track_id:
            return

        track = sp.track(track_id)
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        
        query = f"{track_name} {artist_name}"
        await play_youtube_search_simple(interaction, query)

    except Exception as e:
        logger.error(f"Simple Spotify track error: {e}")

async def play_spotify_playlist_simple(interaction, url):
    """Simplified Spotify playlist for button interactions"""
    try:
        playlist_id = extract_spotify_playlist_id(url)
        if not playlist_id:
            return

        playlist = sp.playlist(playlist_id)
        tracks = playlist['tracks']['items']

        if not tracks:
            return

        # Just play the first track for button interactions
        track_item = tracks[0]
        if track_item['track']:
            track = track_item['track']
            name = track['name']
            artist = track['artists'][0]['name']
            query = f"{name} {artist}"
            await play_youtube_search_simple(interaction, query)

    except Exception as e:
        logger.error(f"Simple Spotify playlist error: {e}")

async def play_youtube_search(interaction, query, spotify_link=None, track_name=None, artist_name=None):
    """Search and play from YouTube with enhanced audio quality"""
    try:
        search_query = query
        music_keywords = ['song', 'music', 'audio', 'track', 'lyrics', 'official']
        if not any(keyword in query.lower() for keyword in music_keywords):
            search_query = f"{query} song"
            
        logger.info(f"Searching YouTube for: {search_query} in guild: {interaction.guild.name}")
        info = ytdl.extract_info(f"ytsearch:{search_query}", download=False)
        if not info.get('entries'):
            await interaction.followup.send("❌ No results found on YouTube.")
            return

        video_info = info['entries'][0]
        
        # Enhanced audio format selection for better quality
        formats = video_info.get('formats', [])
        audio_url = None
        
        # Priority: m4a audio > best audio format > fallback
        for fmt in formats:
            if (fmt.get('acodec', 'none') != 'none' and 
                fmt.get('vcodec', 'none') == 'none' and 
                fmt.get('ext') == 'm4a'):
                audio_url = fmt.get('url')
                break
                
        if not audio_url:
            for fmt in formats:
                if (fmt.get('acodec', 'none') != 'none' and 
                    fmt.get('vcodec', 'none') == 'none'):
                    audio_url = fmt.get('url')
                    break
                
        if not audio_url:
            audio_url = video_info.get('url')
            
        if not audio_url:
            await interaction.followup.send("❌ Could not find audio stream.")
            return
            
        title = video_info.get('title', 'Unknown Title')
        webpage_url = video_info.get('webpage_url', '')
        duration = video_info.get('duration', 0)
        
        if duration:
            minutes, seconds = divmod(duration, 60)
            duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "Unknown"

        # Enhanced audio source with better quality settings and dynamic volume
        guild_queue = get_guild_queue(interaction.guild.id)
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                audio_url,
                executable=FFMPEG_PATH,
                **get_ffmpeg_options()
            ),
            volume=guild_queue.volume
        )

        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        def after_playing(error):
            if error is None and interaction.guild.id not in paused_guilds:
                asyncio.run_coroutine_threadsafe(wait_for_song_completion(interaction), bot.loop)
        
        voice_client.play(source, after=after_playing)
        
        # Store current song info per guild
        if spotify_link and track_name and artist_name:
            current_song_info[interaction.guild.id] = f"{track_name} by {artist_name}"
            embed = discord.Embed(
                title="🎵 Now Playing (from Spotify)",
                description=f"**{track_name}** by **{artist_name}**",
                color=0x1db954
            )
            embed.add_field(name="Spotify Link", value=f"[Open in Spotify]({spotify_link})", inline=False)
            embed.add_field(name="Playing from YouTube", value=f"[{title}]({webpage_url})", inline=False)
            embed.add_field(name="Duration", value=duration_str, inline=True)
        else:
            current_song_info[interaction.guild.id] = title
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"[{title}]({webpage_url})",
                color=0x00ff00
            )
            embed.add_field(name="Duration", value=duration_str, inline=True)
            embed.add_field(name="Searched for", value=f"`{query}`", inline=True)
        
        # Show dashboard with music controls
        guild_queue = get_guild_queue(interaction.guild.id)
        embed.add_field(name="Queue", value=f"{guild_queue.size()} songs waiting", inline=True)
        embed.add_field(name="Auto-Play", value="🔄 ON" if guild_queue.is_auto_play else "❌ OFF", inline=True)
        embed.add_field(name="Server", value=interaction.guild.name, inline=True)
        embed.add_field(name="Quality", value="🎧 High Quality Audio", inline=True)
        
        view = MusicDashboardView(interaction.guild.id)
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        logger.error(f"YouTube search error in guild {interaction.guild.name}: {e}")
        await interaction.followup.send(f"❌ YouTube error: {e}")

async def play_youtube(interaction, url_or_query):
    """Play audio from YouTube with enhanced quality"""
    try:
        if not ('youtube.com' in url_or_query or 'youtu.be' in url_or_query):
            url_or_query = f"ytsearch:{url_or_query}"
            
        logger.info(f"Extracting info for: {url_or_query} in guild: {interaction.guild.name}")
        info = ytdl.extract_info(url_or_query, download=False)
        
        if not info:
            await interaction.followup.send("❌ Could not extract video information.")
            return
            
        if 'entries' in info:
            if not info['entries']:
                await interaction.followup.send("❌ No results found for your search.")
                return
            info = info['entries'][0]
        
        if not info:
            await interaction.followup.send("❌ Could not find video information.")
            return
        
        title = info.get('title', 'Unknown Title')
        webpage_url = info.get('webpage_url', '')
        duration = info.get('duration', 0)
        
        # Enhanced audio format selection
        formats = info.get('formats', [])
        audio_url = None
        
        for fmt in formats:
            if (fmt.get('acodec', 'none') != 'none' and 
                fmt.get('vcodec', 'none') == 'none' and 
                fmt.get('ext') == 'm4a'):
                audio_url = fmt.get('url')
                break
                
        if not audio_url:
            for fmt in formats:
                if (fmt.get('acodec', 'none') != 'none' and 
                    fmt.get('vcodec', 'none') == 'none'):
                    audio_url = fmt.get('url')
                    break
                    
        if not audio_url:
            audio_url = info.get('url')
            
        if not audio_url:
            await interaction.followup.send("❌ Could not find audio stream.")
            return
        
        if duration:
            minutes, seconds = divmod(duration, 60)
            duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "Unknown"

        guild_queue = get_guild_queue(interaction.guild.id)
        source = discord.FFmpegPCMAudio(
            audio_url,
            executable=FFMPEG_PATH,
            **get_ffmpeg_options(guild_queue.volume)
        )

        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        voice_client.play(source)
        
        current_song_info[interaction.guild.id] = title
        
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{title}]({webpage_url})",
            color=0x00ff00
        )
        embed.add_field(name="Duration", value=duration_str, inline=True)
        embed.add_field(name="Server", value=interaction.guild.name, inline=True)
        embed.add_field(name="Quality", value="🎧 High Quality Audio", inline=True)
        
        guild_queue = get_guild_queue(interaction.guild.id)
        embed.add_field(name="Queue", value=f"{guild_queue.size()} songs waiting", inline=True)
        embed.add_field(name="Auto-Play", value="🔄 ON" if guild_queue.is_auto_play else "❌ OFF", inline=True)
        
        view = MusicDashboardView(interaction.guild.id)
        await interaction.followup.send(embed=embed, view=view)
        
    except Exception as e:
        logger.error(f"YouTube playback error in guild {interaction.guild.name}: {e}")
        await interaction.followup.send(f"❌ YouTube error: {e}")

async def play_spotify_track(interaction, url):
    """Play a Spotify track by searching for it on YouTube"""
    try:
        track_id = extract_spotify_track_id(url)
        if not track_id:
            await interaction.followup.send("❌ Invalid Spotify track URL.")
            return

        track = sp.track(track_id)
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        spotify_link = track['external_urls']['spotify']
        
        query = f"{track_name} {artist_name}"
        await play_youtube_search(interaction, query, spotify_link, track_name, artist_name)

    except Exception as e:
        logger.error(f"Spotify track error in guild {interaction.guild.name}: {e}")
        await interaction.followup.send(f"❌ Spotify error: {e}")

async def play_spotify_playlist(interaction, url):
    """Add all tracks from Spotify playlist to queue"""
    try:
        playlist_id = extract_spotify_playlist_id(url)
        if not playlist_id:
            await interaction.followup.send("❌ Invalid Spotify playlist URL.")
            return

        playlist = sp.playlist(playlist_id)
        playlist_name = playlist['name']
        tracks = playlist['tracks']['items']

        if not tracks:
            await interaction.followup.send("❌ Playlist is empty.")
            return

        guild_queue = get_guild_queue(interaction.guild.id)
        
        track_count = 0
        for track_item in tracks:
            if track_item['track']:
                track = track_item['track']
                name = track['name']
                artist = track['artists'][0]['name']
                query = f"{name} {artist}"
                guild_queue.add(query)
                track_count += 1

        embed = discord.Embed(
            title="📀 Playlist Added",
            description=f"Added {track_count} tracks from **{playlist_name}** to the queue",
            color=0x1db954
        )
        embed.add_field(name="Server", value=interaction.guild.name, inline=True)
        await interaction.followup.send(embed=embed)
        
        if not interaction.guild.voice_client.is_playing():
            next_song = guild_queue.next()
            if next_song:
                await start_playback(interaction, next_song)

    except Exception as e:
        logger.error(f"Spotify playlist error in guild {interaction.guild.name}: {e}")
        await interaction.followup.send(f"❌ Playlist error: {e}")

def extract_spotify_track_id(url):
    """Extract Spotify track ID from URL"""
    match = re.search(r'track/([a-zA-Z0-9]+)', url)
    return match.group(1) if match else None

def extract_spotify_playlist_id(url):
    """Extract Spotify playlist ID from URL"""
    match = re.search(r'playlist/([a-zA-Z0-9]+)', url)
    return match.group(1) if match else None

@bot.tree.command(name='dashboard', description="Open the music player dashboard with all controls")
async def dashboard(interaction: discord.Interaction):
    """Show the interactive music player dashboard"""
    try:
        guild_queue = get_guild_queue(interaction.guild.id)
        voice_client = interaction.guild.voice_client
        
        embed = discord.Embed(title="🎵 Music Player Dashboard", color=0x00ff00)
        embed.add_field(name="Server", value=interaction.guild.name, inline=True)
        
        if voice_client and voice_client.is_playing():
            current_song = current_song_info.get(interaction.guild.id, "Unknown Song")
            embed.add_field(name="🎵 Now Playing", value=current_song, inline=False)
            embed.add_field(name="Status", value="▶️ Playing", inline=True)
        elif voice_client and voice_client.is_paused():
            current_song = current_song_info.get(interaction.guild.id, "Unknown Song")
            embed.add_field(name="🎵 Current Song", value=current_song, inline=False)
            embed.add_field(name="Status", value="⏸️ Paused", inline=True)
        else:
            embed.add_field(name="Status", value="⏹️ Stopped", inline=True)
        
        embed.add_field(name="Queue", value=f"{guild_queue.size()} songs waiting", inline=True)
        embed.add_field(name="Auto-Play", value="🔄 ON" if guild_queue.is_auto_play else "❌ OFF", inline=True)
        embed.add_field(name="Volume", value=f"🔊 {guild_queue.get_volume_percentage()}%", inline=True)
        embed.add_field(name="Quality", value="🎧 High Quality Audio", inline=True)
        
        view = MusicDashboardView(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)
    except Exception as e:
        logger.error(f"Dashboard error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message(f"❌ Dashboard error: {e}", ephemeral=True)

@bot.tree.command(name='skip', description="Skip the current song")
async def skip(interaction: discord.Interaction):
    try:
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            guild_queue = get_guild_queue(interaction.guild.id)
            if not guild_queue.is_empty():
                await interaction.response.send_message("⏭️ Skipped. Playing next song...")
            else:
                await interaction.response.send_message("⏭️ Skipped. No more songs in queue.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
    except Exception as e:
        logger.error(f"Skip error in guild {interaction.guild.name}: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Skip error occurred", ephemeral=True)

@bot.tree.command(name='queue', description="Show the current song queue")
async def queue_command(interaction: discord.Interaction):
    try:
        guild_queue = get_guild_queue(interaction.guild.id)
        
        if guild_queue.is_empty():
            await interaction.response.send_message("❌ Queue is empty.")
            return
        
        embed = discord.Embed(title="🎵 Current Queue", color=0x00ff00)
        embed.add_field(name="Server", value=interaction.guild.name, inline=True)
        
        queue_list = []
        for i, song in enumerate(guild_queue.queue[:10]):
            queue_list.append(f"{i + 1}. {song}")
        
        if len(guild_queue.queue) > 10:
            queue_list.append(f"... and {len(guild_queue.queue) - 10} more songs")
        
        embed.description = "\n".join(queue_list) if queue_list else "Queue is empty"
        embed.add_field(name="Total Songs", value=str(guild_queue.size()), inline=True)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logger.error(f"Queue command error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message(f"❌ Queue error: {e}", ephemeral=True)

@bot.tree.command(name='pause', description="Pause the current song")
async def pause(interaction: discord.Interaction):
    try:
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
    except Exception as e:
        logger.error(f"Pause error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message("❌ Pause error occurred", ephemeral=True)

@bot.tree.command(name='resume', description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    try:
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)
    except Exception as e:
        logger.error(f"Resume error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message("❌ Resume error occurred", ephemeral=True)

@bot.tree.command(name='join', description="Join your voice channel")
async def join(interaction: discord.Interaction):
    try:
        if not interaction.user.voice:
            await interaction.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
            return
        
        if interaction.guild.voice_client:
            await interaction.response.send_message("❌ Already connected to a voice channel.", ephemeral=True)
            return
            
        voice_client = await interaction.user.voice.channel.connect()
        guild_voice_clients[interaction.guild.id] = voice_client
        await interaction.response.send_message(f"🎧 Joined {interaction.user.voice.channel.name} in {interaction.guild.name}")
    except Exception as e:
        logger.error(f"Join error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message(f"❌ Failed to join: {e}")

@bot.tree.command(name='leave', description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    try:
        voice_client = interaction.guild.voice_client
        if voice_client:
            guild_queue = get_guild_queue(interaction.guild.id)
            guild_queue.clear()
            if interaction.guild.id in current_song_info:
                del current_song_info[interaction.guild.id]
            if interaction.guild.id in guild_voice_clients:
                del guild_voice_clients[interaction.guild.id]
            await voice_client.disconnect()
            await interaction.response.send_message(f"👋 Left the voice channel in {interaction.guild.name} and cleared queue.")
        else:
            await interaction.response.send_message("❌ Not connected to a voice channel.", ephemeral=True)
    except Exception as e:
        logger.error(f"Leave error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message("❌ Leave error occurred", ephemeral=True)

@bot.tree.command(name='clear', description="Clear the song queue")
async def clear(interaction: discord.Interaction):
    try:
        guild_queue = get_guild_queue(interaction.guild.id)
        guild_queue.clear()
        await interaction.response.send_message(f"🗑️ Queue cleared for {interaction.guild.name}.")
    except Exception as e:
        logger.error(f"Clear error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message("❌ Clear error occurred", ephemeral=True)

@bot.tree.command(name='stop', description="Stop music and clear queue")
async def stop(interaction: discord.Interaction):
    try:
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            guild_queue = get_guild_queue(interaction.guild.id)
            guild_queue.clear()
            if interaction.guild.id in current_song_info:
                del current_song_info[interaction.guild.id]
            await interaction.response.send_message(f"⏹️ Stopped music and cleared queue for {interaction.guild.name}.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
    except Exception as e:
        logger.error(f"Stop error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message("❌ Stop error occurred", ephemeral=True)

@bot.tree.command(name='nowplaying', description="Show what's currently playing")
async def nowplaying(interaction: discord.Interaction):
    try:
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            current_song = current_song_info.get(interaction.guild.id, "Unknown Song")
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=current_song,
                color=0x00ff00
            )
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            embed.add_field(name="Quality", value="🎧 High Quality Audio", inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
    except Exception as e:
        logger.error(f"Now playing error in guild {interaction.guild.name}: {e}")
        await interaction.response.send_message("❌ Now playing error occurred", ephemeral=True)

@bot.tree.command(name='ping', description="Check bot's latency and status")
async def ping(interaction: discord.Interaction):
    try:
        latency = round(bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Bot Status",
            color=0x00ff00
        )
        embed.add_field(name="Latency", value=f"{latency}ms", inline=True)
        embed.add_field(name="Status", value="🟢 Online", inline=True)
        embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Voice Connections", value=str(len([g for g in bot.guilds if g.voice_client])), inline=True)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logger.error(f"Ping error: {e}")
        await interaction.response.send_message("❌ Ping error occurred", ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error(f"Command error in {ctx.guild.name if ctx.guild else 'DM'}: {error}")

@bot.event
async def on_application_command_error(interaction: discord.Interaction, error):
    logger.error(f"Application command error in {interaction.guild.name if interaction.guild else 'DM'}: {error}")
    if not interaction.response.is_done():
        try:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)
        except:
            pass

@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates for better multi-server management"""
    if member == bot.user:
        return
    
    try:
        voice_client = member.guild.voice_client
        if voice_client and voice_client.channel:
            # Check if bot is alone in voice channel
            non_bot_members = [m for m in voice_client.channel.members if not m.bot]
            if len(non_bot_members) == 0:
                # Wait 60 seconds then disconnect if still alone
                await asyncio.sleep(60)
                if voice_client and voice_client.channel:
                    current_non_bot = [m for m in voice_client.channel.members if not m.bot]
                    if len(current_non_bot) == 0:
                        logger.info(f"Auto-disconnecting from {member.guild.name} due to inactivity")
                        guild_queue = get_guild_queue(member.guild.id)
                        guild_queue.clear()
                        if member.guild.id in current_song_info:
                            del current_song_info[member.guild.id]
                        if member.guild.id in guild_voice_clients:
                            del guild_voice_clients[member.guild.id]
                        await voice_client.disconnect()
    except Exception as e:
        logger.error(f"Voice state update error in {member.guild.name}: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)