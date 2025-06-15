# Render Deployment Guide for Discord Music Bot

## Step-by-Step Deployment Instructions

### 1. Prepare Your Repository

Make sure your project has these files:
- `discord_music_bot.py` (main bot file)
- `render.yaml` (deployment configuration)
- `Dockerfile` (container configuration)
- `pyproject.toml` (Python dependencies)

### 2. Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub account
3. Connect your GitHub repository

### 3. Deploy on Render

#### Option A: Using Render Dashboard

1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Choose "Docker" as the environment
4. Set these configurations:
   - **Name**: `discord-music-bot`
   - **Environment**: `Docker`
   - **Build Command**: Leave empty (Docker handles this)
   - **Start Command**: Leave empty (Docker handles this)
   - **Plan**: Free (for testing)

#### Option B: Using render.yaml (Automatic)

1. Push your code with `render.yaml` to GitHub
2. Render will automatically detect and deploy

### 4. Set Environment Variables

In Render Dashboard → Your Service → Environment:

```
DISCORD_BOT_TOKEN=your_actual_discord_bot_token
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
```

**Important**: Remove the hardcoded tokens from your code before deploying publicly!

### 5. Configure Build Settings

- **Build Command**: `docker build -t discord-bot .`
- **Start Command**: `python discord_music_bot.py`

### 6. Deploy and Monitor

1. Click "Create Web Service"
2. Wait for deployment (5-10 minutes)
3. Check logs for "Bot is ready!" message

## Troubleshooting

### Common Issues:

1. **FFmpeg not found**
   - Solution: Dockerfile includes FFmpeg installation

2. **Opus library errors**
   - Solution: PyNaCl and libopus are included in dependencies

3. **Bot doesn't respond**
   - Check environment variables are set correctly
   - Verify Discord bot token is valid
   - Check bot permissions in Discord server

4. **Memory issues**
   - Upgrade from Free tier if needed
   - Monitor resource usage in Render dashboard

### Required Discord Bot Permissions:
- Send Messages
- Use Slash Commands
- Connect to Voice Channels
- Speak in Voice Channels
- Use Voice Activity

## Cost Information

- **Free Tier**: 750 hours/month, sufficient for testing
- **Starter Plan**: $7/month for always-on service
- **Pro Plan**: $25/month for production use

## Alternative Deployment Methods

### Using Git Integration:
1. Push to GitHub with all deployment files
2. Render auto-detects and deploys
3. Automatic redeployment on git push

### Manual Deployment:
1. Upload files directly to Render
2. Configure settings manually
3. Deploy from Render dashboard

## Post-Deployment

1. Test bot commands in Discord
2. Monitor logs for errors
3. Set up automatic deployments from GitHub
4. Configure domain if needed (Pro tier)

## Security Notes

- Never commit API tokens to public repositories
- Use environment variables for all secrets
- Enable GitHub secret scanning
- Regularly rotate API keys

Your bot will be running 24/7 on Render with these configurations!