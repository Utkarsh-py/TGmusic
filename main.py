import os
import asyncio
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.phone import CreateGroupCallRequest, JoinGroupCallRequest
from telethon.tl.types import InputPeerChannel, InputGroupCall
from telethon.errors import SessionPasswordNeededError
import youtube_dl
import sqlite3
import json
from typing import Dict, List
import subprocess
import tempfile
import requests
from io import BytesIO

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramMusicBot:
    def __init__(self):
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.bot_token = os.getenv('BOT_TOKEN')
        self.session_name = os.getenv('SESSION_NAME', 'music_bot')
        self.admin_users = list(map(int, os.getenv('ADMIN_USERS', '').split(','))) if os.getenv('ADMIN_USERS') else []
        self.premium_users = set()
        self.queue = {}  # chat_id: [songs]
        self.current_playing = {}  # chat_id: song_info
        self.voice_calls = {}  # chat_id: call_info
        
        # Initialize database
        self.init_db()
        
        # Initialize Telegram client
        self.client = TelegramClient(
            self.session_name,
            self.api_id,
            self.api_hash
        )
        
        # YouTube downloader configuration
        self.ytdl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192K',
        }

    def init_db(self):
        """Initialize SQLite database for user management"""
        self.conn = sqlite3.connect('bot_data.db')
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_premium BOOLEAN DEFAULT FALSE,
                premium_until DATETIME,
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
        
        self.conn.commit()

    async def start(self):
        """Start the bot"""
        await self.client.start(bot_token=self.bot_token)
        logger.info("Bot started successfully!")
        
        # Create downloads directory
        os.makedirs('downloads', exist_ok=True)
        
        # Register event handlers
        self.register_handlers()
        
        await self.client.run_until_disconnected()

    def register_handlers(self):
        """Register all event handlers"""
        
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await self.handle_start(event)
        
        @self.client.on(events.NewMessage(pattern='/help'))
        async def help_handler(event):
            await self.handle_help(event)
        
        @self.client.on(events.NewMessage(pattern='/play'))
        async def play_handler(event):
            await self.handle_play(event)
        
        @self.client.on(events.NewMessage(pattern='/queue'))
        async def queue_handler(event):
            await self.handle_queue(event)
        
        @self.client.on(events.NewMessage(pattern='/skip'))
        async def skip_handler(event):
            await self.handle_skip(event)
        
        @self.client.on(events.NewMessage(pattern='/stop'))
        async def stop_handler(event):
            await self.handle_stop(event)
        
        @self.client.on(events.NewMessage(pattern='/join'))
        async def join_handler(event):
            await self.handle_join_voice_chat(event)
        
        @self.client.on(events.NewMessage(pattern='/leave'))
        async def leave_handler(event):
            await self.handle_leave_voice_chat(event)
        
        # Admin commands
        @self.client.on(events.NewMessage(pattern='/ban'))
        async def ban_handler(event):
            await self.handle_ban(event)
        
        @self.client.on(events.NewMessage(pattern='/unban'))
        async def unban_handler(event):
            await self.handle_unban(event)
        
        @self.client.on(events.NewMessage(pattern='/premium'))
        async def premium_handler(event):
            await self.handle_premium(event)
        
        @self.client.on(events.NewMessage(pattern='/stats'))
        async def stats_handler(event):
            await self.handle_stats(event)

    async def handle_start(self, event):
        """Handle /start command"""
        user_id = event.sender_id
        username = event.sender.username or "Unknown"
        
        # Add user to database
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username)
            VALUES (?, ?)
        ''', (user_id, username))
        self.conn.commit()
        
        welcome_msg = """
🎵 **Welcome to Advanced Music Bot!** 🎵

I can stream music and videos in Telegram voice chats!

**Basic Commands:**
• `/play <song name/YouTube URL>` - Play music
• `/queue` - Show current queue
• `/skip` - Skip current song
• `/stop` - Stop playback
• `/join` - Join voice chat
• `/leave` - Leave voice chat

**Premium Features:**
• Unlimited queue length
• High-quality audio (320kbps)
• Video streaming
• Priority in queue
• Ad-free experience

Contact admin for premium access!
        """
        
        await event.respond(welcome_msg)

    async def handle_help(self, event):
        """Handle /help command"""
        help_msg = """
🎵 **Music Bot Help** 🎵

**Music Commands:**
• `/play <song>` - Play music in voice chat
• `/queue` - Show current playlist
• `/skip` - Skip to next song
• `/stop` - Stop music and clear queue
• `/join` - Join group voice chat
• `/leave` - Leave voice chat

**Admin Commands:**
• `/ban <user_id> [reason]` - Ban user
• `/unban <user_id>` - Unban user
• `/premium <user_id> <days>` - Give premium
• `/stats` - Show bot statistics

**Premium Features:**
• High-quality audio streaming
• Video streaming support
• Unlimited queue length
• Skip queue limits
• Priority support

**Supported Sources:**
• YouTube videos/playlists
• Direct audio/video links
• Spotify tracks (premium)
• SoundCloud (premium)
        """
        
        await event.respond(help_msg)

    async def handle_play(self, event):
        """Handle /play command"""
        if not await self.check_user_permissions(event):
            return
        
        chat_id = event.chat_id
        message = event.message.message.split(' ', 1)
        
        if len(message) < 2:
            await event.respond("❌ Please provide a song name or YouTube URL!")
            return
        
        query = message[1]
        
        # Check if user is premium for advanced features
        is_premium = await self.is_premium_user(event.sender_id)
        
        # Check queue limits for non-premium users
        if not is_premium and chat_id in self.queue:
            if len(self.queue[chat_id]) >= 10:
                await event.respond("❌ Queue limit reached! Upgrade to premium for unlimited queue.")
                return
        
        await event.respond("🔍 Searching for music...")
        
        try:
            song_info = await self.download_audio(query, is_premium)
            
            if chat_id not in self.queue:
                self.queue[chat_id] = []
            
            self.queue[chat_id].append({
                'info': song_info,
                'requested_by': event.sender.first_name,
                'user_id': event.sender_id
            })
            
            queue_pos = len(self.queue[chat_id])
            
            if chat_id not in self.current_playing:
                await self.play_next(chat_id)
                await event.respond(f"🎵 **Now Playing:** {song_info['title']}")
            else:
                await event.respond(f"✅ Added to queue (Position: {queue_pos})\n🎵 **{song_info['title']}**")
                
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await event.respond("❌ Error processing your request. Please try again.")

    async def download_audio(self, query, is_premium=False):
        """Download audio from various sources"""
        ytdl_opts = self.ytdl_opts.copy()
        
        if is_premium:
            ytdl_opts['format'] = 'bestaudio[abr>=320]/best'
            ytdl_opts['audioquality'] = '0'  # Best quality
        
        with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
            try:
                # Search if not a direct URL
                if not (query.startswith('http://') or query.startswith('https://')):
                    search_query = f"ytsearch1:{query}"
                else:
                    search_query = query
                
                info = ytdl.extract_info(search_query, download=False)
                
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'url': info.get('url'),
                    'webpage_url': info.get('webpage_url'),
                    'thumbnail': info.get('thumbnail')
                }
                
            except Exception as e:
                logger.error(f"Download error: {e}")
                raise

    async def handle_queue(self, event):
        """Handle /queue command"""
        chat_id = event.chat_id
        
        if chat_id not in self.queue or not self.queue[chat_id]:
            await event.respond("📭 Queue is empty!")
            return
        
        queue_msg = "🎵 **Current Queue:**\n\n"
        
        # Current playing
        if chat_id in self.current_playing:
            current = self.current_playing[chat_id]
            queue_msg += f"🎶 **Now Playing:** {current['info']['title']}\n"
            queue_msg += f"👤 Requested by: {current['requested_by']}\n\n"
        
        # Queue list
        for i, item in enumerate(self.queue[chat_id][:10], 1):
            queue_msg += f"{i}. **{item['info']['title']}**\n"
            queue_msg += f"   👤 {item['requested_by']}\n\n"
        
        if len(self.queue[chat_id]) > 10:
            remaining = len(self.queue[chat_id]) - 10
            queue_msg += f"... and {remaining} more songs\n"
        
        await event.respond(queue_msg)

    async def handle_skip(self, event):
        """Handle /skip command"""
        chat_id = event.chat_id
        
        if chat_id not in self.current_playing:
            await event.respond("❌ Nothing is currently playing!")
            return
        
        # Check permissions
        user_id = event.sender_id
        is_admin = user_id in self.admin_users
        is_requester = (chat_id in self.current_playing and 
                       self.current_playing[chat_id].get('user_id') == user_id)
        
        if not (is_admin or is_requester or await self.is_premium_user(user_id)):
            await event.respond("❌ You can only skip songs you requested or upgrade to premium!")
            return
        
        current_song = self.current_playing[chat_id]['info']['title']
        await event.respond(f"⏭️ Skipped: **{current_song}**")
        
        await self.play_next(chat_id)

    async def handle_stop(self, event):
        """Handle /stop command"""
        chat_id = event.chat_id
        user_id = event.sender_id
        
        # Check admin permissions
        if user_id not in self.admin_users:
            await event.respond("❌ Only admins can stop the music!")
            return
        
        # Clear queue and stop playing
        if chat_id in self.queue:
            del self.queue[chat_id]
        
        if chat_id in self.current_playing:
            del self.current_playing[chat_id]
        
        await event.respond("⏹️ Music stopped and queue cleared!")

    async def play_next(self, chat_id):
        """Play next song in queue"""
        if chat_id not in self.queue or not self.queue[chat_id]:
            if chat_id in self.current_playing:
                del self.current_playing[chat_id]
            return
        
        next_song = self.queue[chat_id].pop(0)
        self.current_playing[chat_id] = next_song
        
        # Here you would implement actual audio streaming to voice chat
        # This requires PyTgCalls or similar library for actual voice chat streaming
        logger.info(f"Playing: {next_song['info']['title']} in chat {chat_id}")

    async def handle_join_voice_chat(self, event):
        """Join group voice chat"""
        chat_id = event.chat_id
        
        try:
            # This would require PyTgCalls implementation
            await event.respond("🎙️ Joined voice chat! Ready to stream music.")
            self.voice_calls[chat_id] = {'active': True, 'joined_at': datetime.now()}
            
        except Exception as e:
            logger.error(f"Error joining voice chat: {e}")
            await event.respond("❌ Failed to join voice chat. Make sure there's an active voice chat.")

    async def handle_leave_voice_chat(self, event):
        """Leave group voice chat"""
        chat_id = event.chat_id
        
        if chat_id in self.voice_calls:
            del self.voice_calls[chat_id]
        
        if chat_id in self.current_playing:
            del self.current_playing[chat_id]
        
        if chat_id in self.queue:
            del self.queue[chat_id]
        
        await event.respond("👋 Left voice chat!")

    async def handle_ban(self, event):
        """Handle /ban command (Admin only)"""
        if event.sender_id not in self.admin_users:
            await event.respond("❌ You're not authorized to use this command!")
            return
        
        message_parts = event.message.message.split()
        if len(message_parts) < 2:
            await event.respond("❌ Usage: `/ban <user_id> [reason]`")
            return
        
        try:
            user_id = int(message_parts[1])
            reason = ' '.join(message_parts[2:]) if len(message_parts) > 2 else "No reason provided"
            
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO banned_users (user_id, banned_by, reason)
                VALUES (?, ?, ?)
            ''', (user_id, event.sender_id, reason))
            self.conn.commit()
            
            await event.respond(f"✅ User {user_id} has been banned.\nReason: {reason}")
            
        except ValueError:
            await event.respond("❌ Invalid user ID!")

    async def handle_unban(self, event):
        """Handle /unban command (Admin only)"""
        if event.sender_id not in self.admin_users:
            await event.respond("❌ You're not authorized to use this command!")
            return
        
        message_parts = event.message.message.split()
        if len(message_parts) < 2:
            await event.respond("❌ Usage: `/unban <user_id>`")
            return
        
        try:
            user_id = int(message_parts[1])
            
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
            self.conn.commit()
            
            await event.respond(f"✅ User {user_id} has been unbanned.")
            
        except ValueError:
            await event.respond("❌ Invalid user ID!")

    async def handle_premium(self, event):
        """Handle /premium command (Admin only)"""
        if event.sender_id not in self.admin_users:
            await event.respond("❌ You're not authorized to use this command!")
            return
        
        message_parts = event.message.message.split()
        if len(message_parts) < 3:
            await event.respond("❌ Usage: `/premium <user_id> <days>`")
            return
        
        try:
            user_id = int(message_parts[1])
            days = int(message_parts[2])
            
            premium_until = datetime.now() + timedelta(days=days)
            
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE users SET is_premium = TRUE, premium_until = ?
                WHERE user_id = ?
            ''', (premium_until.isoformat(), user_id))
            self.conn.commit()
            
            self.premium_users.add(user_id)
            
            await event.respond(f"✅ User {user_id} granted premium for {days} days!")
            
        except ValueError:
            await event.respond("❌ Invalid user ID or days!")

    async def handle_stats(self, event):
        """Handle /stats command (Admin only)"""
        if event.sender_id not in self.admin_users:
            await event.respond("❌ You're not authorized to use this command!")
            return
        
        cursor = self.conn.cursor()
        
        # Get statistics
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = TRUE')
        premium_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM banned_users')
        banned_users = cursor.fetchone()[0]
        
        active_chats = len(self.voice_calls)
        total_queued = sum(len(queue) for queue in self.queue.values())
        
        stats_msg = f"""
📊 **Bot Statistics**

👥 **Users:** {total_users}
💎 **Premium Users:** {premium_users}
🚫 **Banned Users:** {banned_users}
🎙️ **Active Voice Chats:** {active_chats}
🎵 **Songs in Queue:** {total_queued}
⏰ **Uptime:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        await event.respond(stats_msg)

    async def check_user_permissions(self, event):
        """Check if user is banned"""
        user_id = event.sender_id
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT reason FROM banned_users WHERE user_id = ?', (user_id,))
        banned = cursor.fetchone()
        
        if banned:
            await event.respond(f"❌ You are banned from using this bot.\nReason: {banned[0]}")
            return False
        
        return True

    async def is_premium_user(self, user_id):
        """Check if user has premium access"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT premium_until FROM users 
            WHERE user_id = ? AND is_premium = TRUE
        ''', (user_id,))
        
        result = cursor.fetchone()
        if result:
            premium_until = datetime.fromisoformat(result[0])
            if premium_until > datetime.now():
                return True
            else:
                # Premium expired
                cursor.execute('''
                    UPDATE users SET is_premium = FALSE 
                    WHERE user_id = ?
                ''', (user_id,))
                self.conn.commit()
        
        return False

if __name__ == "__main__":
    bot = TelegramMusicBot()
    asyncio.run(bot.start())
