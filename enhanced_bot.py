import os
import asyncio
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped, VideoPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, HighQualityVideo
from pytgcalls.exceptions import NoActiveGroupCall
import yt_dlp
import sqlite3
import json
from typing import Dict, List
import aiohttp
import aiofiles
from pathlib import Path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class EnhancedMusicBot:
    def __init__(self):
        # Environment variables
        self.api_id = int(os.getenv('API_ID'))
        self.api_hash = os.getenv('API_HASH')
        self.bot_token = os.getenv('BOT_TOKEN')
        self.session_name = os.getenv('SESSION_NAME', 'enhanced_music_bot')
        self.admin_users = list(map(int, filter(None, os.getenv('ADMIN_USERS', '').split(','))))
        
        # Bot state
        self.queue = {}  # chat_id: [songs]
        self.current_playing = {}  # chat_id: song_info
        self.premium_users = set()
        self.user_sessions = {}
        
        # Initialize database
        self.init_db()
        
        # Initialize clients
        self.app = TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash
        )
        
        self.call_py = PyTgCalls(self.app)
        
        # YT-DLP configuration
        self.ytdl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'keepvideo': True,
        }
        
        # Create necessary directories
        Path("downloads").mkdir(exist_ok=True)
        Path("sessions").mkdir(exist_ok=True)

    def init_db(self):
        """Initialize SQLite database"""
        self.conn = sqlite3.connect('enhanced_bot_data.db', check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_premium BOOLEAN DEFAULT FALSE,
                premium_until DATETIME,
                total_songs_played INTEGER DEFAULT 0,
                join_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Banned users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_by INTEGER,
                reason TEXT,
                banned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Premium transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                duration_days INTEGER,
                payment_method TEXT,
                transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'completed'
            )
        ''')
        
        # Songs history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS song_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                song_title TEXT,
                song_url TEXT,
                duration INTEGER,
                played_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()

    async def start(self):
        """Start the enhanced bot"""
        await self.app.start(bot_token=self.bot_token)
        await self.call_py.start()
        
        logger.info("Enhanced Music Bot started successfully!")
        
        # Register event handlers
        self.register_handlers()
        
        # Start background tasks
        asyncio.create_task(self.cleanup_old_files())
        asyncio.create_task(self.update_premium_status())
        
        await self.app.run_until_disconnected()

    def register_handlers(self):
        """Register all event handlers"""
        
        @self.app.on(events.NewMessage(pattern=r'/start'))
        async def start_handler(event):
            await self.handle_start(event)
        
        @self.app.on(events.NewMessage(pattern=r'/help'))
        async def help_handler(event):
            await self.handle_help(event)
        
        @self.app.on(events.NewMessage(pattern=r'/play'))
        async def play_handler(event):
            await self.handle_play(event)
        
        @self.app.on(events.NewMessage(pattern=r'/vplay'))
        async def vplay_handler(event):
            await self.handle_video_play(event)
        
        @self.app.on(events.NewMessage(pattern=r'/queue'))
        async def queue_handler(event):
            await self.handle_queue(event)
        
        @self.app.on(events.NewMessage(pattern=r'/skip'))
        async def skip_handler(event):
            await self.handle_skip(event)
        
        @self.app.on(events.NewMessage(pattern=r'/stop'))
        async def stop_handler(event):
            await self.handle_stop(event)
        
        @self.app.on(events.NewMessage(pattern=r'/pause'))
        async def pause_handler(event):
            await self.handle_pause(event)
        
        @self.app.on(events.NewMessage(pattern=r'/resume'))
        async def resume_handler(event):
            await self.handle_resume(event)
        
        @self.app.on(events.NewMessage(pattern=r'/volume'))
        async def volume_handler(event):
            await self.handle_volume(event)
        
        @self.app.on(events.NewMessage(pattern=r'/current'))
        async def current_handler(event):
            await self.handle_current(event)
        
        # Admin commands
        @self.app.on(events.NewMessage(pattern=r'/ban'))
        async def ban_handler(event):
            await self.handle_ban(event)
        
        @self.app.on(events.NewMessage(pattern=r'/unban'))
        async def unban_handler(event):
            await self.handle_unban(event)
        
        @self.app.on(events.NewMessage(pattern=r'/premium'))
        async def premium_handler(event):
            await self.handle_grant_premium(event)
        
        @self.app.on(events.NewMessage(pattern=r'/stats'))
        async def stats_handler(event):
            await self.handle_stats(event)
        
        @self.app.on(events.NewMessage(pattern=r'/broadcast'))
        async def broadcast_handler(event):
            await self.handle_broadcast(event)
        
        # Premium purchase commands
        @self.app.on(events.NewMessage(pattern=r'/buy_premium'))
        async def buy_premium_handler(event):
            await self.handle_buy_premium(event)
        
        # Callback handlers for PyTgCalls
        @self.call_py.on_stream_end()
        async def stream_end_handler(_, update):
            await self.on_stream_end(update)

    async def handle_start(self, event):
        """Enhanced start command"""
        user_id = event.sender_id
        user = await event.get_sender()
        username = getattr(user, 'username', None)
        first_name = getattr(user, 'first_name', 'User')
        
        # Add user to database
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        self.conn.commit()
        
        is_premium = await self.is_premium_user(user_id)
        premium_text = "💎 **PREMIUM USER**" if is_premium else ""
        
        welcome_msg = f"""
🎵 **Welcome to Enhanced Music Bot!** 🎵
{premium_text}

Hi {first_name}! I can stream high-quality music and videos in Telegram voice chats!

**🎶 Music Commands:**
• `/play <song>` - Play audio in voice chat
• `/vplay <video>` - Play video in voice chat  
• `/queue` - Show current playlist
• `/skip` - Skip current song
• `/pause` - Pause playback
• `/resume` - Resume playback
• `/stop` - Stop and clear queue
• `/volume <1-200>` - Adjust volume
• `/current` - Show current playing song

**💎 Premium Features:**
• 🎵 High-quality audio (320kbps)
• 🎥 HD video streaming (720p)
• ⏭️ Unlimited skips
• 📝 Unlimited queue length  
• 🚀 Priority in queue
• 📊 Advanced statistics
• ❌ Ad-free experience

**💰 Get Premium:**
• `/buy_premium` - Purchase premium access
• Monthly: $5.99 | Yearly: $59.99

Join voice chat first, then use music commands!
        """
        
        await event.respond(welcome_msg)

    async def handle_play(self, event):
        """Handle audio play command"""
        if not await self.check_permissions(event):
            return
        
        chat_id = event.chat_id
        message_parts = event.message.message.split(' ', 1)
        
        if len(message_parts) < 2:
            await event.respond("❌ **Usage:** `/play <song name or URL>`")
            return
        
        query = message_parts[1]
        is_premium = await self.is_premium_user(event.sender_id)
        
        # Check queue limits
        if not is_premium and chat_id in self.queue and len(self.queue[chat_id]) >= 10:
            await event.respond("❌ **Queue limit reached!** Upgrade to premium for unlimited queue.")
            return
        
        status_msg = await event.respond("🔍 **Searching for music...**")
        
        try:
            song_info = await self.download_media(query, is_premium, media_type='audio')
            
            if not song_info:
                await status_msg.edit("❌ **Could not find the requested song.**")
                return
            
            # Add to queue
            queue_item = {
                'info': song_info,
                'requested_by': event.sender.first_name,
                'user_id': event.sender_id,
                'type': 'audio',
                'chat_id': chat_id
            }
            
            if chat_id not in self.queue:
                self.queue[chat_id] = []
            
            self.queue[chat_id].append(queue_item)
            
            # Start playing if nothing is currently playing
            if chat_id not in self.current_playing:
                await self.play_next_in_queue(chat_id)
                await status_msg.edit(f"🎵 **Now Playing:**\n**{song_info['title']}**\n👤 Requested by {event.sender.first_name}")
            else:
                queue_position = len(self.queue[chat_id])
                await status_msg.edit(f"✅ **Added to queue (#{queue_position})**\n🎵 **{song_info['title']}**\n👤 {event.sender.first_name}")
                
        except Exception as e:
            logger.error(f"Play command error: {e}")
            await status_msg.edit("❌ **Error processing your request. Please try again.**")

    async def handle_video_play(self, event):
        """Handle video play command"""
        if not await self.check_permissions(event):
            return
        
        is_premium = await self.is_premium_user(event.sender_id)
        if not is_premium:
            await event.respond("❌ **Video streaming is a premium feature!**\n💎 Use `/buy_premium` to upgrade.")
            return
        
        chat_id = event.chat_id
        message_parts = event.message.message.split(' ', 1)
        
        if len(message_parts) < 2:
            await event.respond("❌ **Usage:** `/vplay <video name or URL>`")
            return
        
        query = message_parts[1]
        status_msg = await event.respond("🔍 **Searching for video...**")
        
        try:
            video_info = await self.download_media(query, is_premium=True, media_type='video')
            
            if not video_info:
                await status_msg.edit("❌ **Could not find the requested video.**")
                return
            
            # Add to queue
            queue_item = {
                'info': video_info,
                'requested_by': event.sender.first_name,
                'user_id': event.sender_id,
                'type': 'video',
                'chat_id': chat_id
            }
            
            if chat_id not in self.queue:
                self.queue[chat_id] = []
            
            self.queue[chat_id].append(queue_item)
            
            # Start playing if nothing is currently playing
            if chat_id not in self.current_playing:
                await self.play_next_in_queue(chat_id)
                await status_msg.edit(f"🎥 **Now Playing Video:**\n**{video_info['title']}**\n👤 Requested by {event.sender.first_name}")
            else:
                queue_position = len(self.queue[chat_id])
                await status_msg.edit(f"✅ **Added to queue (#{queue_position})**\n🎥 **{video_info['title']}**\n👤 {event.sender.first_name}")
                
        except Exception as e:
            logger.error(f"Video play command error: {e}")
            await status_msg.edit("❌ **Error processing your request. Please try again.**")

    async def download_media(self, query, is_premium=False, media_type='audio'):
        """Download audio or video with yt-dlp"""
        ytdl_opts = self.ytdl_opts.copy()
        
        if media_type == 'audio':
            if is_premium:
                ytdl_opts['format'] = 'bestaudio[abr>=320]/bestaudio/best'
            else:
                ytdl_opts['format'] = 'bestaudio[abr<=128]/bestaudio/best'
        else:  # video
            ytdl_opts['format'] = 'best[height<=720]/best'
        
        with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
            try:
                # Search if not a direct URL
                if not (query.startswith('http://') or query.startswith('https://')):
                    search_query = f"ytsearch1:{query}"
                else:
                    search_query = query
                
                info = ytdl.extract_info(search_query, download=True)
                
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                
                # Get the downloaded file path
                file_path = ytdl.prepare_filename(info)
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'file_path': file_path,
                    'webpage_url': info.get('webpage_url'),
                    'thumbnail': info.get('thumbnail'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0)
                }
                
            except Exception as e:
                logger.error(f"Download error: {e}")
                return None

    async def play_next_in_queue(self, chat_id):
        """Play next song in queue using PyTgCalls"""
        if chat_id not in self.queue or not self.queue[chat_id]:
            if chat_id in self.current_playing:
                del self.current_playing[chat_id]
            return
        
        next_item = self.queue[chat_id].pop(0)
        self.current_playing[chat_id] = next_item
        
        try:
            file_path = next_item['info']['file_path']
            
            if next_item['type'] == 'audio':
                # Audio stream
                audio_quality = HighQualityAudio() if await self.is_premium_user(next_item['user_id']) else None
                stream = AudioPiped(file_path, audio_parameters=audio_quality)
            else:
                # Video stream  
                video_quality = HighQualityVideo()
                audio_quality = HighQualityAudio()
                stream = AudioVideoPiped(file_path, audio_parameters=audio_quality, video_parameters=video_quality)
            
            await self.call_py.join_group_call(
                chat_id,
                stream,
                stream_type=StreamType().pulse_stream
            )
            
            # Log to history
            await self.log_song_history(next_item)
            
        except NoActiveGroupCall:
            logger.warning(f"No active voice chat in {chat_id}")
            # Try to play next song
            await self.play_next_in_queue(chat_id)
        except Exception as e:
            logger.error(f"Error playing media: {e}")
            # Try to play next song
            await self.play_next_in_queue(chat_id)

    async def on_stream_end(self, update):
        """Handle stream end event"""
        chat_id = update.chat_id
        await self.play_next_in_queue(chat_id)

    async def handle_queue(self, event):
        """Show current queue"""
        chat_id = event.chat_id
        
        if chat_id not in self.queue or not self.queue[chat_id]:
            if chat_id in self.current_playing:
                current = self.current_playing[chat_id]
                msg = f"🎵 **Currently Playing:**\n**{current['info']['title']}**\n👤 {current['requested_by']}\n\n📭 **Queue is empty**"
            else:
                msg = "📭 **Nothing is playing and queue is empty**"
            await event.respond(msg)
            return
        
        queue_msg = "🎵 **Music Queue:**\n\n"
        
        # Current playing
        if chat_id in self.current_playing:
            current = self.current_playing[chat_id]
            media_icon = "🎥" if current['type'] == 'video' else "🎵"
            queue_msg += f"{media_icon} **Now Playing:** {current['info']['title']}\n👤 {current['requested_by']}\n\n"
        
        # Queue items
        queue_msg += "**📝 Up Next:**\n"
        for i, item in enumerate(self.queue[chat_id][:10], 1):
            media_icon = "🎥" if item['type'] == 'video' else "🎵"
            queue_msg += f"{i}. {media_icon} **{item['info']['title']}**\n   👤 {item['requested_by']}\n\n"
        
        if len(self.queue[chat_id]) > 10:
            remaining = len(self.queue[chat_id]) - 10
            queue_msg += f"... and **{remaining}** more songs\n"
        
        await event.respond(queue_msg)

    async def handle_skip(self, event):
        """Skip current song"""
        chat_id = event.chat_id
        user_id = event.sender_id
        
        if chat_id not in self.current_playing:
            await event.respond("❌ **Nothing is currently playing!**")
            return
        
        # Check permissions
        is_admin = user_id in self.admin_users
        is_requester = self.current_playing[chat_id].get('user_id') == user_id
        is_premium = await self.is_premium_user(user_id)
        
        if not (is_admin or is_requester or is_premium):
            await event.respond("❌ **You can only skip songs you requested!**\n💎 Premium users can skip any song.")
            return
        
        current_song = self.current_playing[chat_id]['info']['title']
        
        try:
            await self.call_py.leave_group_call(chat_id)
        except:
            pass
        
        await self.play_next_in_queue(chat_id)
        await event.respond(f"⏭️ **Skipped:** {current_song}")

    async def handle_pause(self, event):
        """Pause current playback"""
        chat_id = event.chat_id
        
        try:
            await self.call_py.pause_stream(chat_id)
            await event.respond("⏸️ **Music paused**")
        except Exception as e:
            await event.respond("❌ **Nothing is playing or failed to pause**")

    async def handle_resume(self, event):
        """Resume paused playback"""
        chat_id = event.chat_id
        
        try:
            await self.call_py.resume_stream(chat_id)
            await event.respond("▶️ **Music resumed**")
        except Exception as e:
            await event.respond("❌ **Nothing is paused or failed to resume**")

    async def handle_volume(self, event):
        """Adjust volume"""
        message_parts = event.message.message.split()
        if len(message_parts) < 2:
            await event.respond("❌ **Usage:** `/volume <1-200>`")
            return
        
        try:
            volume = int(message_parts[1])
            if volume < 1 or volume > 200:
                await event.respond("❌ **Volume must be between 1-200**")
                return
            
            chat_id = event.chat_id
            await self.call_py.change_volume_call(chat_id, volume)
            await event.respond(f"🔊 **Volume set to {volume}%**")
            
        except ValueError:
            await event.respond("❌ **Please provide a valid number (1-200)**")
        except Exception as e:
            await event.respond("❌ **Failed to change volume**")

    async def handle_current(self, event):
        """Show current playing song info"""
        chat_id = event.chat_id
        
        if chat_id not in self.current_playing:
            await event.respond("❌ **Nothing is currently playing**")
            return
        
        current = self.current_playing[chat_id]
        info = current['info']
        media_icon = "🎥" if current['type'] == 'video' else "🎵"
        
        duration_formatted = f"{info['duration'] // 60}:{info['duration'] % 60:02d}" if info['duration'] else "Unknown"
        
        current_msg = f"""
{media_icon} **Currently Playing:**

**📝 Title:** {info['title']}
**👤 Requested by:** {current['requested_by']}
**⏱️ Duration:** {duration_formatted}
**👁️ Views:** {info.get('view_count', 'Unknown')}
**📺 Uploader:** {info.get('uploader', 'Unknown')}
        """
        
        await event.respond(current_msg)

    async def handle_buy_premium(self, event):
        """Handle premium purchase"""
        user_id = event.sender_id
        
        if await self.is_premium_user(user_id):
            # Show current premium status
            cursor = self.conn.cursor()
            cursor.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if result:
                premium_until = datetime.fromisoformat(result[0])
                days_left = (premium_until - datetime.now()).days
                await event.respond(f"💎 **You already have premium!**\n⏰ **Expires in:** {days_left} days")
                return
        
        premium_msg = """
💎 **Premium Subscription Plans**

**Monthly Plan - $5.99**
• 🎵 High-quality audio (320kbps)
• 🎥 HD video streaming (720p)
• ⏭️ Unlimited skips
• 📝 Unlimited queue length
• 🚀 Priority in queue
• 📊 Advanced statistics
• ❌ Ad-free experience

**Yearly Plan - $59.99** (Save $12!)
• All monthly features
• 💰 Best value
• 🎁 2 months free

**Payment Methods:**
• 💳 Credit/Debit Card
• 💰 PayPal
• ₿ Cryptocurrency
• 🏦 Bank Transfer

**To purchase, contact admin:**
@your_admin_username

Or use inline payment: /pay_premium
        """
        
        await event.respond(premium_msg)

    async def log_song_history(self, queue_item):
        """Log played song to history"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO song_history (chat_id, user_id, song_title, song_url, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            queue_item['chat_id'],
            queue_item['user_id'],
            queue_item['info']['title'],
            queue_item['info'].get('webpage_url', ''),
            queue_item['info'].get('duration', 0)
        ))
        
        # Update user's song count
        cursor.execute('''
            UPDATE users SET total_songs_played = total_songs_played + 1
            WHERE user_id = ?
        ''', (queue_item['user_id'],))
        
        self.conn.commit()

    async def cleanup_old_files(self):
        """Background task to cleanup old downloaded files"""
        while True:
            try:
                downloads_path = Path("downloads")
                cutoff_time = datetime.now() - timedelta(hours=2)
                
                for file_path in downloads_path.glob("*"):
                    if file_path.stat().st_mtime < cutoff_time.timestamp():
                        file_path.unlink(missing_ok=True)
                        logger.info(f"Cleaned up old file: {file_path}")
                
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            
            await asyncio.sleep(3600)  # Run every hour

    async def update_premium_status(self):
        """Background task to update premium status"""
        while True:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    UPDATE users SET is_premium = FALSE 
                    WHERE is_premium = TRUE AND premium_until < ?
                ''', (datetime.now().isoformat(),))
                
                expired_count = cursor.rowcount
                if expired_count > 0:
                    logger.info(f"Expired premium for {expired_count} users")
                
                self.conn.commit()
                
            except Exception as e:
                logger.error(f"Premium update error: {e}")
            
            await asyncio.sleep(3600)  # Check every hour

    async def check_permissions(self, event):
        """Check if user has permission to use the bot"""
        user_id = event.sender_id
        
        # Check if banned
        cursor = self.conn.cursor()
        cursor.execute('SELECT reason FROM banned_users WHERE user_id = ?', (user_id,))
        banned = cursor.fetchone()
        
        if banned:
            await event.respond(f"❌ **You are banned from using this bot**\n📝 **Reason:** {banned[0]}")
            return False
        
        return True

    async def is_premium_user(self, user_id):
        """Check if user has active premium"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT premium_until FROM users 
            WHERE user_id = ? AND is_premium = TRUE
        ''', (user_id,))
        
        result = cursor.fetchone()
        if result:
            premium_until = datetime.fromisoformat(result[0])
            return premium_until > datetime.now()
        
        return False

    # Add all other handler methods (ban, unban, stats, etc.) here...
    # [Previous handler methods from the first version would go here]

if __name__ == "__main__":
    bot = EnhancedMusicBot()
    asyncio.run(bot.start())
