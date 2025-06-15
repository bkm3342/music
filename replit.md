# Discord Music Bot

## Overview

This is a feature-rich Discord music bot built with Python that allows users to play music from YouTube and Spotify in Discord voice channels. The bot provides comprehensive queue management, playback controls, and uses modern Discord slash commands for user interaction.

## System Architecture

### Core Technologies
- **Python 3.11+**: Main programming language
- **discord.py**: Discord API wrapper for bot functionality
- **yt-dlp**: YouTube video/audio downloading and streaming
- **spotipy**: Spotify Web API integration
- **FFmpeg**: Audio processing and streaming to Discord

### Bot Architecture
The bot follows a single-file architecture pattern with clear separation of concerns:
- Configuration management through environment variables
- Modular service initialization (Discord, Spotify, YouTube)
- Event-driven command handling using Discord's slash command system
- Asynchronous processing for all audio operations

## Key Components

### 1. Discord Bot Core (`discord_music_bot.py`)
- **Purpose**: Main bot application with command handlers and interactive dashboard
- **Architecture**: Uses discord.py's command framework with slash commands and UI components
- **Authentication**: Token-based authentication via environment variables
- **Intents**: Configured for message content and voice state management
- **Multi-Server Support**: Isolated queues and settings per Discord server

### 2. Enhanced Audio Processing Pipeline
- **YouTube Integration**: yt-dlp with optimized format selection for high-quality audio
- **Spotify Integration**: spotipy for track/playlist metadata, searches YouTube for actual audio
- **FFmpeg**: Enhanced audio encoding with 192k bitrate, 48kHz sample rate, and volume optimization
- **Audio Quality**: Prioritizes M4A formats and high-quality streams for better sound

### 3. Advanced Queue Management System
- **Design**: In-memory queue management isolated per Discord server
- **Features**: Auto-play toggle, queue progression, skip functionality, status display
- **Multi-Server**: Each server maintains independent queues and settings
- **Persistence**: No persistent storage (queues reset on bot restart)

### 4. Enhanced Interactive Music Dashboard with Audio Effects
- **Basic Controls**: Pause, Resume, Skip, Auto-Play toggle, Queue view, Clear queue, Stop & Leave
- **Audio Effects**: Bass Boost, Nightcore, Slowed + Reverb buttons with real-time application
- **Volume Controls**: Instant volume adjustment with visual feedback bars
- **Real-time Updates**: Dynamic button states and server-specific information with effect indicators
- **User Experience**: Organized 3-row layout with visual feedback and ephemeral responses

### 5. Advanced Voice Activity Detection System
- **Auto-Pause/Resume**: Automatically pauses music when voice channel is empty, resumes when members join
- **Smart Activity Monitoring**: Detects real-time voice channel member changes
- **Connection Handling**: Automatic voice channel joining/leaving with multi-server support
- **Audio Streaming**: Real-time high-quality audio streaming with enhanced error handling
- **Auto-Disconnect**: Automatically leaves voice channels when inactive for 60 seconds
- **Server Isolation**: Independent voice connections for each Discord server

### 6. Audio Effects Processing System
- **Bass Boost**: Enhanced low-frequency amplification with equalizer filters
- **Nightcore**: Increased tempo and pitch for energetic sound
- **Slowed + Reverb**: Reduced tempo with atmospheric reverb effects
- **Real-time Application**: Effects apply to currently playing songs without interruption
- **Effect Persistence**: Settings maintained per server across song changes

## Data Flow

1. **User Input**: Slash commands received from Discord users
2. **Content Resolution**: 
   - YouTube URLs/searches → Direct yt-dlp processing
   - Spotify URLs → API metadata extraction → YouTube search → yt-dlp processing
3. **Queue Management**: Add tracks to server-specific queues
4. **Audio Streaming**: FFmpeg processes audio and streams to Discord voice channels
5. **User Feedback**: Rich embed messages with playback status and queue information

## External Dependencies

### Required Services
- **Discord API**: Bot token required for Discord integration
- **YouTube**: No API key required (uses yt-dlp's built-in access)
- **Spotify Web API**: Optional - requires client ID and secret for Spotify integration

### System Dependencies
- **FFmpeg**: Must be installed and accessible in system PATH
- **Python Packages**: discord.py, yt-dlp, spotipy (managed via pyproject.toml)

### Environment Variables
- `DISCORD_BOT_TOKEN`: Required Discord bot token
- `SPOTIFY_CLIENT_ID`: Optional Spotify application client ID
- `SPOTIFY_CLIENT_SECRET`: Optional Spotify application client secret

## Deployment Strategy

### Replit Configuration
- **Runtime**: Python 3.11 environment with Nix package management
- **Dependencies**: Auto-installation via pip during startup
- **Execution**: Parallel workflow execution with automatic dependency resolution

### Production Considerations
- Bot runs as a single persistent process
- No database required (stateless design)
- Requires stable internet connection for audio streaming
- Memory usage scales with concurrent voice channel connections

### Scalability Limitations
- Single-instance design (no horizontal scaling)
- In-memory queue storage (no persistence across restarts)
- FFmpeg dependency requires system-level installation

## Changelog

```
Changelog:
- June 15, 2025: Initial setup
- June 15, 2025: Fixed YouTube playback errors with improved audio format detection
- June 15, 2025: Added PyNaCl for full voice support 
- June 15, 2025: Enhanced error handling and logging for better troubleshooting
- June 15, 2025: Added interactive music player dashboard with button controls
- June 15, 2025: Implemented auto-play toggle functionality for queue management
- June 15, 2025: Created comprehensive music control interface with pause/resume/skip/stop buttons
- June 15, 2025: Enhanced multi-server support with isolated queues and settings per Discord server
- June 15, 2025: Upgraded audio quality with 192k bitrate, 48kHz sample rate, and M4A format priority
- June 15, 2025: Fixed interaction acknowledgment errors and improved error handling across all commands
- June 15, 2025: Added auto-disconnect feature and server-specific voice channel management
- June 15, 2025: Added volume up/down controls with dynamic FFmpeg volume processing
- June 15, 2025: Fixed skip button to properly play next song from queue with auto-play integration
- June 15, 2025: Implemented server-specific volume settings with real-time adjustment feedback
- June 15, 2025: Fixed volume controls to prevent song interruption and interaction timeout errors
- June 15, 2025: Enhanced skip button with immediate queue progression and seamless audio transitions
- June 15, 2025: Implemented PCMVolumeTransformer for real-time volume adjustment without song interruption
- June 15, 2025: Fixed pause button to properly pause/resume without triggering random song playback
- June 15, 2025: Added paused state tracking to prevent automatic song progression when music is paused
- June 15, 2025: Updated volume controls to edit existing messages instead of creating new ones for cleaner chat
- June 15, 2025: Added live ping command to monitor bot latency and responsiveness
- June 15, 2025: Enhanced error handling and state management for better multi-server reliability
- June 15, 2025: Removed web dashboard interface as requested by user
- June 15, 2025: Upgraded audio quality to 320k bitrate with enhanced FFmpeg processing for maximum quality
- June 15, 2025: Implemented advanced voice activity detection with auto-pause/resume functionality
- June 15, 2025: Added comprehensive audio effects system (Bass Boost, Nightcore, Slowed + Reverb)
- June 15, 2025: Enhanced music dashboard with 3-row button layout and real-time audio effect controls
- June 15, 2025: Integrated seamless effect switching without song interruption using background processing
- June 15, 2025: Added persistent audio effect settings per server with visual feedback indicators
- June 15, 2025: Fixed critical auto-play bug when using audio effects - effects now apply to current song without triggering next song
```

## User Preferences

```
Preferred communication style: Simple, everyday language.
```