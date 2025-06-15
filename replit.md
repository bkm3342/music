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
- **Purpose**: Main bot application with command handlers
- **Architecture**: Uses discord.py's command framework with slash commands
- **Authentication**: Token-based authentication via environment variables
- **Intents**: Configured for message content and voice state management

### 2. Audio Processing Pipeline
- **YouTube Integration**: yt-dlp for audio extraction and streaming
- **Spotify Integration**: spotipy for track/playlist metadata, searches YouTube for actual audio
- **FFmpeg**: Handles audio encoding and streaming to Discord voice channels

### 3. Queue Management System
- **Design**: In-memory queue management for each Discord server
- **Features**: Queue progression, skip functionality, status display
- **Persistence**: No persistent storage (queues reset on bot restart)

### 4. Voice Channel Management
- **Connection Handling**: Automatic voice channel joining/leaving
- **Audio Streaming**: Real-time audio streaming with queue management
- **Error Handling**: Graceful handling of connection issues and audio failures

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
- June 15, 2025. Initial setup
```

## User Preferences

```
Preferred communication style: Simple, everyday language.
```