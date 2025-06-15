import discord
from discord.ext import commands
import yt_dlp
import spotipy
import re
import asyncio
import os
import logging
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

# Enhanced FFmpeg options for better audio quality
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 50M -analyzeduration 50M',
    'options': '-vn -filter:a "volume=0.8" -ar 48000 -ac 2 -b:a 192k'
}

# Global storage - separated by guild for multi-server support
current_guild_queues = {}
current_song_info = {}
guild_voice_clients = {}

class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.is_auto_play = True
        self.loop_current = False
        self.loop_queue = False
        
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
                await interaction.response.send_message("⏸️ Music paused", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing is playing", ephemeral=True)
        except Exception as e:
            logger.error(f"Pause button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)
            
    @discord.ui.button(label="▶️ Resume", style=discord.ButtonStyle.success, row=0)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await interaction.response.send_message("▶️ Music resumed", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing is paused", ephemeral=True)
        except Exception as e:
            logger.error(f"Resume button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)
            
    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary, row=0)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                await interaction.response.send_message("⏭️ Song skipped", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing is playing", ephemeral=True)
        except Exception as e:
            logger.error(f"Skip button error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error occurred", ephemeral=True)
            
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
        
    @discord.ui.button(label="🗑️ Clear Queue", style=discord.ButtonStyle.danger, row=1)
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

async def wait_for_song_completion(interaction):
    """Wait for current song to complete and handle queue progression"""
    try:
        while interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            await asyncio.sleep(2)
        
        guild_queue = get_guild_queue(interaction.guild.id)
        if guild_queue.is_auto_play and not guild_queue.is_empty():
            next_song = guild_queue.next()
            await interaction.followup.send(f"🎵 Auto-Playing Next: {next_song}")
            await start_playback(interaction, next_song)
    except Exception as e:
        logger.error(f"Wait for song completion error: {e}")

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

        # Enhanced audio source with better quality settings
        source = discord.FFmpegPCMAudio(
            audio_url,
            executable=FFMPEG_PATH,
            **FFMPEG_OPTIONS
        )

        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        voice_client.play(source)
        
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

        source = discord.FFmpegPCMAudio(
            audio_url,
            executable=FFMPEG_PATH,
            **FFMPEG_OPTIONS
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
        
        embed.add_field(name="Queue Size", value=f"{guild_queue.size()} songs", inline=True)
        embed.add_field(name="Auto-Play", value="🔄 ON" if guild_queue.is_auto_play else "❌ OFF", inline=True)
        embed.add_field(name="Audio Quality", value="🎧 High Quality", inline=True)
        
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