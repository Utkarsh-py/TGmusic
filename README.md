# 🎵 Advanced Telegram Music Bot

A powerful Telegram bot that can stream high-quality music and videos in real-time voice chats with admin controls and premium features.

## ✨ Features

### 🎶 Music Streaming
- **High-quality audio streaming** (up to 320kbps for premium)
- **HD video streaming** (720p for premium users)
- **Real-time voice chat streaming** using PyTgCalls
- **YouTube, Spotify, SoundCloud** support
- **Queue management** with unlimited length for premium
- **Playback controls** (play, pause, resume, skip, stop)
- **Volume control** (1-200%)

### 👑 Admin Features
- **User management** (ban/unban users)
- **Premium management** (grant premium access)
- **Bot statistics** and analytics
- **Broadcast messages** to all users
- **Song history** and user activity logs

### 💎 Premium Features
- **320kbps high-quality audio**
- **720p HD video streaming**
- **Unlimited queue length**
- **Priority in queue**
- **Unlimited skips**
- **Advanced statistics**
- **Ad-free experience**

### 🛡️ Security & Performance
- **SQLite database** for user management
- **Automatic file cleanup**
- **Premium status management**
- **Error handling** and logging
- **Docker support** for easy deployment

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Telegram API credentials
- Bot token from [@BotFather](https://t.me/botfather)

### 1. Clone Repository
```bash
git clone https://github.com/Utkarsh-py/TGmusic.git
cd telegram-music-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create `.env` file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
ADMIN_USERS=123456789,987654321
```

### 4. Run the Bot
```bash
python main.py
```

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)
```bash
# Clone repository
git clone https://github.com/yourusername/telegram-music-bot.git
cd telegram-music-bot

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start services
docker-compose up -d
```

### Using Docker
```bash
# Build image
docker build -t telegram-music-bot .

# Run container
docker run -d \
  --name music-bot \
  -e API_ID=your_api_id \
  -e API_HASH=your_api_hash \
  -e BOT_TOKEN=your_bot_token \
  -e ADMIN_USERS=123456789 \
  -v $(pwd)/downloads:/app/downloads \
  telegram-music-bot
```

## ☁️ Cloud Deployment

### Deploy on Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Utkarsh-py/TGmusic)

1. Click the deploy button
2. Fill in the required environment variables
3. Click "Deploy app"

### Deploy on Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template/TGmusic)

### Deploy on Render
1. Fork this repository
2. Connect to Render
3. Set environment variables
4. Deploy

### Deploy on VPS/Server
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3 python3-pip ffmpeg git -y

# Clone repository
git clone https://github.com/yourusername/telegram-music-bot.git
cd telegram-music-bot

# Install Python dependencies
pip3 install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your credentials

# Create systemd service
sudo nano /etc/systemd/system/music-bot.service
```

Add to service file:
```ini
[Unit]
Description=Telegram Music Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telegram-music-bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable music-bot
sudo systemctl start music-bot
```

## 📋 Commands

### 🎵 Music Commands
- `/start` - Start the bot and show welcome message
- `/help` - Show help message with all commands
- `/play <song>` - Play audio in voice chat
- `/vplay <video>` - Play video in voice chat (Premium)
- `/queue` - Show current playlist
- `/skip` - Skip current song
- `/pause` - Pause playback
- `/resume` - Resume playback
- `/stop` - Stop music and clear queue
- `/volume <1-200>` - Adjust volume
- `/current` - Show current playing song info

### 👑 Admin Commands
- `/ban <user_id> [reason]` - Ban user from using bot
- `/unban <user_id>` - Unban user
- `/premium <user_id> <days>` - Grant premium access
- `/stats` - Show bot statistics
- `/broadcast <message>` - Broadcast message to all users

### 💎 Premium Commands
- `/buy_premium` - Show premium plans and purchase options

## 🔧 Configuration

### Environment Variables
```env
# Required
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token_from_botfather

# Optional
SESSION_NAME=music_bot
ADMIN_USERS=123456789,987654321
MAX_QUEUE_SIZE=50
DEFAULT_VOLUME=70
LOG_LEVEL=INFO

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost/musicbot
REDIS_URL=redis://localhost:6379

# Premium Features
PREMIUM_MONTHLY_COST=5.99
PAYMENT_PROVIDER_TOKEN=your_payment_token

# External APIs (optional)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SOUNDCLOUD_CLIENT_ID=your_soundcloud_client_id
```

### Getting Telegram Credentials

1. **API ID and Hash:**
   - Go to [my.telegram.org](https://my.telegram.org)
   - Log in with your phone number
   - Go to "API development tools"
   - Create a new application
   - Copy API ID and API Hash

2. **Bot Token:**
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` command
   - Follow the instructions
   - Copy the bot token

3. **Admin User IDs:**
   - Message [@userinfobot](https://t.me/userinfobot)
   - Forward a message from admin users
   - Copy their user IDs

## 📁 Project Structure

```
telegram-music-bot/
├── main.py                 # Main bot application
├── enhanced_bot.py         # Enhanced bot with PyTgCalls
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker container config
├── docker-compose.yml     # Docker Compose config
├── .env.example          # Environment variables template
├── README.md             # This file
├── downloads/            # Downloaded music files
├── sessions/             # Telegram session files
└── data/                 # Database and logs
```

## 🎯 Usage Examples

### Basic Music Playback
```
User: /play Shape of You
Bot: 🎵 Now Playing: Shape of You - Ed Sheeran
     👤 Requested by John

User: /play https://youtu.be/JGwWNGJdvx8
Bot: ✅ Added to queue (#2)
     🎵 Perfect - Ed Sheeran
     👤 John
```

### Video Streaming (Premium)
```
User: /vplay Despacito music video
Bot: 🎥 Now Playing Video: Despacito - Luis Fonsi ft. Daddy Yankee
     👤 Requested by Premium User
```

### Queue Management
```
User: /queue
Bot: 🎵 Music Queue:

     🎶 Now Playing: Shape of You - Ed Sheeran
     👤 John

     📝 Up Next:
     1. 🎵 Perfect - Ed Sheeran
        👤 John
     2. 🎵 Thinking Out Loud - Ed Sheeran
        👤 Jane
```

### Admin Controls
```
Admin: /ban 123456789 Spam
Bot: ✅ User 123456789 has been banned.
     Reason: Spam

Admin: /stats
Bot: 📊 Bot Statistics
     👥 Users: 1,234
     💎 Premium Users: 156
     🎙️ Active Voice Chats: 23
```

## 🔧 Advanced Features

### Custom Quality Settings
Premium users automatically get:
- **Audio:** 320kbps quality
- **Video:** 720p HD resolution
- **Priority:** Skip queue limitations

### Auto-cleanup
- Downloaded files are automatically cleaned after 2 hours
- Database is optimized regularly
- Logs are rotated to prevent disk space issues

### Premium Management
```python
# Grant premium programmatically
cursor.execute('''
    UPDATE users SET is_premium = TRUE, premium_until = ?
    WHERE user_id = ?
''', (datetime.now() + timedelta(days=30), user_id))
```

## 🐛 Troubleshooting

### Common Issues

1. **"No active group call" error**
   ```
   Solution: Make sure there's an active voice chat in the group
   Admin needs to start voice chat first
   ```

2. **Bot not responding**
   ```
   Check bot token is correct
   Ensure bot is added to group with admin permissions
   Check logs: docker logs music-bot
   ```

3. **Audio quality issues**
   ```
   Update yt-dlp: pip install --upgrade yt-dlp
   Check internet connection
   Try different audio source
   ```

4. **Permission errors**
   ```
   Make sure bot has these permissions:
   - Send messages
   - Delete messages
   - Ban users (for admin features)
   - Manage voice chats
   ```

### Logs and Debugging
```bash
# View logs
docker logs -f music-bot

# Check bot status
systemctl status music-bot

# Debug mode
python main.py --debug
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a Pull Request

### Development Setup
```bash
# Clone repository
git clone https://github.com/Utkarsh-py/TGmusic.git
cd telegram-music-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Run with hot reload
python -m uvicorn main:app --reload
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

- This bot is for educational purposes
- Respect copyright laws in your country
- Use responsibly and follow Telegram's Terms of Service
- The developers are not responsible for misuse

## 📞 Support

- **GitHub Issues:** [Report bugs](https://github.com/Utkarsh-py/TGmusic/issues)
- **Telegram:** [@your_support_bot](https://t.me/friends_4ever_143)
- **Email:** support@yourbot.com
- **Discord:** [Join our server](https://discord.gg/yourserver)

---

**Made with ❤️ by [Utkarsh Pandey](https://github.com/Utkarsh-py)**

⭐ **Don't forget to star this repository if you found it helpful!**
