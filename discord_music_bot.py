import discord
from discord.ext import commands
import yt_dlp
import spotipy
import re
import asyncio
import os
import logging
from spotipy.oauth2 import SpotifyClientCredentials

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Bot Configuration ----
DISCORD_BOT_TOKEN = "MTM4MzY3ODk2MjgzMTU4OTUwOQ.G1uWjY.ctY6kbpI7HQeeec9QIq0NdMGS0LF_vQ_UlDhFg"
SPOTIFY_CLIENT_ID = "56a295f2e2d0424588992d92275cd1c8"  
SPOTIFY_CLIENT_SECRET = "eba3e96a03334f7a832ae5f06ceb48d2"

if not DISCORD_BOT_TOKEN:
    logger.error("DISCORD_BOT_TOKEN environment variable is required")
    exit(1)

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    logger.warning("Spotify credentials not found. Spotify functionality will be disabled.")
    SPOTIFY_ENABLED = False
else:
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

# ---- YouTube & FFmpeg Config ----
FFMPEG_PATH = 'ffmpeg'  # Assumes ffmpeg is in PATH

ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'default_search': 'ytsearch1',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'logtostderr': False,
    'ignoreerrors': False,
    'no_warnings': True,
    'source_address': '0.0.0.0'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# Global song queue
song_queue = []
current_guild_queues = {}

class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        
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

def get_guild_queue(guild_id):
    if guild_id not in current_guild_queues:
        current_guild_queues[guild_id] = MusicQueue()
    return current_guild_queues[guild_id]

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} slash commands globally")
    except Exception as e:
        logger.error(f"❌ Failed to sync commands: {e}")
    
    logger.info(f'✅ Logged in as {bot.user.name}')
    logger.info(f'Bot is ready! Spotify enabled: {SPOTIFY_ENABLED}')

@bot.tree.command(name='play', description="Play a song from YouTube or Spotify")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    
    # Check if user is in voice channel
    if not interaction.user.voice:
        await interaction.followup.send("❌ You need to be in a voice channel to use this command.", ephemeral=True)
        return
    
    # Connect to voice channel if not already connected
    if not interaction.guild.voice_client:
        try:
            await interaction.user.voice.channel.connect()
            logger.info(f"Connected to voice channel: {interaction.user.voice.channel.name}")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to connect to voice channel: {e}")
            return
    
    guild_queue = get_guild_queue(interaction.guild.id)
    
    # If something is already playing, add to queue
    if interaction.guild.voice_client.is_playing():
        guild_queue.add(url)
        await interaction.followup.send(f"🔥 Added to queue: {url} (Position: {guild_queue.size()})")
    else:
        await start_playback(interaction, url)

async def start_playback(interaction, url):
    """Start playing a song and handle queue progression"""
    try:
        if SPOTIFY_ENABLED and 'spotify.com/track/' in url:
            await play_spotify_track(interaction, url)
        elif SPOTIFY_ENABLED and 'spotify.com/playlist/' in url:
            await play_spotify_playlist(interaction, url)
        elif 'youtube.com' in url or 'youtu.be' in url or not ('http' in url):
            await play_youtube(interaction, url)
        else:
            await interaction.followup.send("❌ Invalid URL. Use a YouTube or Spotify link, or provide a search term.")
            return
            
        # Wait for current song to finish, then play next in queue
        await wait_for_song_completion(interaction)
        
    except Exception as e:
        logger.error(f"Error in start_playback: {e}")
        await interaction.followup.send(f"❌ An error occurred: {e}")

async def wait_for_song_completion(interaction):
    """Wait for current song to complete and handle queue progression"""
    while interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        await asyncio.sleep(1)
    
    guild_queue = get_guild_queue(interaction.guild.id)
    if not guild_queue.is_empty():
        next_song = guild_queue.next()
        await interaction.followup.send(f"🎵 Now Playing Next: {next_song}")
        await start_playback(interaction, next_song)

async def play_youtube(interaction, url_or_query):
    """Play audio from YouTube"""
    try:
        # If it's not a URL, treat it as a search query
        if not ('youtube.com' in url_or_query or 'youtu.be' in url_or_query):
            url_or_query = f"ytsearch:{url_or_query}"
            
        info = ytdl.extract_info(url_or_query, download=False)
        
        if 'entries' in info:
            # Search result
            if not info['entries']:
                await interaction.followup.send("❌ No results found for your search.")
                return
            info = info['entries'][0]
        
        stream_url = info['url']
        title = info.get('title', 'Unknown Title')
        webpage_url = info.get('webpage_url', '')
        duration = info.get('duration', 0)
        
        # Format duration
        if duration:
            minutes, seconds = divmod(duration, 60)
            duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "Unknown"

        source = discord.FFmpegPCMAudio(
            stream_url,
            executable=FFMPEG_PATH,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )

        voice_client = interaction.guild.voice_client
        voice_client.stop()
        voice_client.play(source)
        
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"[{title}]({webpage_url})",
            color=0x00ff00
        )
        embed.add_field(name="Duration", value=duration_str, inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"YouTube playback error: {e}")
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
        
        # Search for the track on YouTube
        query = f"{track_name} {artist_name}"
        await play_youtube_search(interaction, query, spotify_link, track_name, artist_name)

    except Exception as e:
        logger.error(f"Spotify track error: {e}")
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
        
        # Add all tracks to queue
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
        await interaction.followup.send(embed=embed)
        
        # If nothing is playing, start with first track
        if not interaction.guild.voice_client.is_playing():
            next_song = guild_queue.next()
            if next_song:
                await start_playback(interaction, next_song)

    except Exception as e:
        logger.error(f"Spotify playlist error: {e}")
        await interaction.followup.send(f"❌ Playlist error: {e}")

async def play_youtube_search(interaction, query, spotify_link=None, track_name=None, artist_name=None):
    """Search and play from YouTube"""
    try:
        info = ytdl.extract_info(f"ytsearch:{query}", download=False)
        if not info.get('entries'):
            await interaction.followup.send("❌ No results found on YouTube.")
            return

        video_info = info['entries'][0]
        stream_url = video_info['url']
        title = video_info.get('title', 'Unknown Title')

        source = discord.FFmpegPCMAudio(
            stream_url,
            executable=FFMPEG_PATH,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )

        voice_client = interaction.guild.voice_client
        voice_client.stop()
        voice_client.play(source)
        
        if spotify_link and track_name and artist_name:
            embed = discord.Embed(
                title="🎵 Now Playing (from Spotify)",
                description=f"**{track_name}** by **{artist_name}**",
                color=0x1db954
            )
            embed.add_field(name="Spotify Link", value=f"[Open in Spotify]({spotify_link})", inline=False)
            embed.add_field(name="Playing from YouTube", value=title, inline=False)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"🎵 Now Playing: {title}")

    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        await interaction.followup.send(f"❌ YouTube search error: {e}")

def extract_spotify_track_id(url):
    """Extract Spotify track ID from URL"""
    match = re.search(r"track/([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None

def extract_spotify_playlist_id(url):
    """Extract Spotify playlist ID from URL"""
    match = re.search(r"playlist/([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None

# ---- Slash Commands ----

@bot.tree.command(name='skip', description="Skip the current song")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_playing():
        await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        return

    voice_client.stop()
    guild_queue = get_guild_queue(interaction.guild.id)
    
    if not guild_queue.is_empty():
        next_song = guild_queue.next()
        await interaction.response.send_message(f"⏭️ Skipped. Now Playing: {next_song}")
        await start_playback(interaction, next_song)
    else:
        await interaction.response.send_message("⏭️ Skipped. No more songs in queue.")

@bot.tree.command(name='queue', description="Show the current song queue")
async def queue_command(interaction: discord.Interaction):
    guild_queue = get_guild_queue(interaction.guild.id)
    
    if guild_queue.is_empty():
        await interaction.response.send_message("❌ Queue is empty.")
        return
    
    embed = discord.Embed(title="🎵 Current Queue", color=0x00ff00)
    
    queue_list = []
    for i, song in enumerate(guild_queue.queue[:10]):  # Show first 10 songs
        queue_list.append(f"{i + 1}. {song}")
    
    if len(guild_queue.queue) > 10:
        queue_list.append(f"... and {len(guild_queue.queue) - 10} more songs")
    
    embed.description = "\n".join(queue_list) if queue_list else "Queue is empty"
    embed.add_field(name="Total Songs", value=str(guild_queue.size()), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='pause', description="Pause the current song")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("⏸️ Paused.")
    else:
        await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

@bot.tree.command(name='resume', description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("▶️ Resumed.")
    else:
        await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

@bot.tree.command(name='join', description="Join your voice channel")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
        return
    
    if interaction.guild.voice_client:
        await interaction.response.send_message("❌ Already connected to a voice channel.", ephemeral=True)
        return
        
    try:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message(f"🎧 Joined {interaction.user.voice.channel.name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to join voice channel: {e}")

@bot.tree.command(name='leave', description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client:
        guild_queue = get_guild_queue(interaction.guild.id)
        guild_queue.clear()
        await voice_client.disconnect()
        await interaction.response.send_message("👋 Left the voice channel and cleared the queue.")
    else:
        await interaction.response.send_message("❌ Not connected to a voice channel.", ephemeral=True)

@bot.tree.command(name='clear', description="Clear the song queue")
async def clear(interaction: discord.Interaction):
    guild_queue = get_guild_queue(interaction.guild.id)
    guild_queue.clear()
    await interaction.response.send_message("🧹 Queue cleared.")

@bot.tree.command(name='stop', description="Stop playback and clear the queue")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    guild_queue = get_guild_queue(interaction.guild.id)
    
    guild_queue.clear()
    if voice_client and voice_client.is_playing():
        voice_client.stop()
    
    await interaction.response.send_message("🛑 Stopped playback and cleared queue.")

@bot.tree.command(name='nowplaying', description="Show information about the current song")
async def nowplaying(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_playing():
        await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
        return
    
    guild_queue = get_guild_queue(interaction.guild.id)
    current_song = guild_queue.current if guild_queue.current else "Unknown"
    
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=current_song,
        color=0x00ff00
    )
    embed.add_field(name="Queue Length", value=str(guild_queue.size()), inline=True)
    
    await interaction.response.send_message(embed=embed)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    logger.error(f"Command error: {error}")

@bot.event
async def on_application_command_error(interaction: discord.Interaction, error):
    logger.error(f"Slash command error: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)

# Voice client error handling
@bot.event
async def on_voice_state_update(member, before, after):
    # If bot is alone in voice channel, disconnect
    if member == bot.user:
        return
    
    voice_client = member.guild.voice_client
    if voice_client and len(voice_client.channel.members) == 1:
        guild_queue = get_guild_queue(member.guild.id)
        guild_queue.clear()
        await voice_client.disconnect()
        logger.info("Left voice channel - no other members present")

if __name__ == "__main__":
    # Start the bot
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
