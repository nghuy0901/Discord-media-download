import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Set

import discord
import requests
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)

# File handler for logging
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8")
file_formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s:%(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler for logging
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Load environment variables from .env (if present)
load_dotenv()

# DISCORD TOKEN: read from environment variable for safety
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "your_actual_bot_token_here")

# Regular expressions for media detection
IMAGE_REGEX = r"https:\/\/cdn\.discordapp\.com\/attachments\/\d*\/\d*\/([a-z0-9\_\-\.]*)\.(jpg|jpeg|png|gif|bmp|webp)(\?.*)?$"
VIDEO_REGEX = r"https:\/\/cdn\.discordapp\.com\/attachments\/\d*\/\d*\/([a-z0-9\_\-\.]*)\.(mp4|avi|mov|mkv|webm|flv)(\?.*)?$"

# Files to store data
HISTORY_FILE = "scan_history.json"
RECOVERY_FILE = "scan_recovery.json"


def is_image(content: str) -> bool:
    """Check if the given URL is an image."""
    return bool(re.match(IMAGE_REGEX, str(content).lower()))


def is_video(content: str) -> bool:
    """Check if the given URL is a video."""
    return bool(re.match(VIDEO_REGEX, str(content).lower()))


def safe_string(text: str) -> str:
    """Convert text to a safe filename string."""
    result_text = ""
    for char in str(text):
        if char.isalnum() or char in ["-", "_", "."]:
            result_text += char
        elif char.isspace():
            result_text += "_"
    
    # Remove consecutive underscores and limit length
    result_text = re.sub(r"_+", "_", result_text).strip("_")
    return result_text[:50] if len(result_text) > 50 else result_text


def format_date(datetime_instance: datetime) -> str:
    """Format datetime to string."""
    return datetime_instance.strftime("%Y-%m-%d_%H-%M-%S")


def format_display_date(datetime_instance: datetime) -> str:
    """Format datetime for display."""
    return datetime_instance.strftime("%d/%m/%Y %H:%M:%S")


def create_folder(server_name: str, channel_name: str) -> str:
    """Create a folder for downloads and return the path."""
    current_path = os.getcwd()
    downloads_folder = os.path.join(current_path, "downloads")
    
    # Create downloads folder if it doesn't exist
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)
    
    server_name = safe_string(server_name)
    channel_name = safe_string(channel_name)
    datetime_str = format_date(datetime.now())
    folder_name = f"{server_name}_{channel_name}_{datetime_str}"

    path = os.path.join(downloads_folder, folder_name)

    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"[+] Created folder: {path}")
    
    return path


async def download_media(url: str, folder: str, file_name: str) -> bool:
    """Download media file from URL."""
    try:
        logger.info(f"[*] Downloading {url} as {file_name}")
        path = os.path.join(folder, file_name)
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(path, "wb") as file:
            file.write(response.content)
        
        logger.info(f"[+] Download successful: {file_name}")
        return True
        
    except Exception as e:
        logger.error(f"[-] Download failed for {file_name}: {str(e)}")
        return False


def convert_byte_to_mb(byte: int) -> float:
    """Convert bytes to megabytes."""
    return round(byte / 1024 / 1024, 3)


class ScanRecovery:
    """Class to manage scan recovery data."""
    
    def __init__(self):
        self.recovery_data = self.load_recovery()
    
    def load_recovery(self) -> Dict:
        """Load recovery data from file."""
        try:
            if os.path.exists(RECOVERY_FILE):
                with open(RECOVERY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[-] Error loading recovery data: {e}")
        return {}
    
    def save_recovery(self):
        """Save recovery data to file."""
        try:
            with open(RECOVERY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.recovery_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[-] Error saving recovery data: {e}")
    
    def start_scan_session(self, channel_id: int, scan_type: str, start_time: datetime, scan_params: Dict):
        """Start a new scan session."""
        channel_key = str(channel_id)
        self.recovery_data[channel_key] = {
            'scan_type': scan_type,
            'start_time': start_time.isoformat(),
            'scan_params': scan_params,
            'status': 'in_progress',
            'last_processed_message': None,
            'processed_count': 0,
            'found_media': 0
        }
        self.save_recovery()
        logger.info(f"[+] Started scan session for channel {channel_id}")
    
    def update_scan_progress(self, channel_id: int, message_id: int, processed_count: int, found_media: int):
        """Update scan progress."""
        channel_key = str(channel_id)
        if channel_key in self.recovery_data:
            self.recovery_data[channel_key]['last_processed_message'] = message_id
            self.recovery_data[channel_key]['processed_count'] = processed_count
            self.recovery_data[channel_key]['found_media'] = found_media
            self.save_recovery()
    
    def complete_scan_session(self, channel_id: int):
        """Mark scan session as completed."""
        channel_key = str(channel_id)
        if channel_key in self.recovery_data:
            self.recovery_data[channel_key]['status'] = 'completed'
            self.save_recovery()
            logger.info(f"[+] Completed scan session for channel {channel_id}")
    
    def get_interrupted_scan(self, channel_id: int) -> Optional[Dict]:
        """Get interrupted scan data for a channel."""
        channel_key = str(channel_id)
        if channel_key in self.recovery_data and self.recovery_data[channel_key]['status'] == 'in_progress':
            return self.recovery_data[channel_key]
        return None
    
    def clear_recovery_data(self, channel_id: int):
        """Clear recovery data for a channel."""
        channel_key = str(channel_id)
        if channel_key in self.recovery_data:
            del self.recovery_data[channel_key]
            self.save_recovery()


class ScanHistory:
    """Class to manage scan history for each channel."""
    
    def __init__(self):
        self.history = self.load_history()
    
    def load_history(self) -> Dict:
        """Load scan history from file."""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[-] Error loading history: {e}")
        return {}
    
    def save_history(self):
        """Save scan history to file."""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[-] Error saving history: {e}")
    
    def get_scanned_urls(self, channel_id: int) -> Set[str]:
        """Get set of already scanned URLs for a channel."""
        channel_key = str(channel_id)
        if channel_key in self.history:
            return set(self.history[channel_key].get('scanned_urls', []))
        return set()
    
    def get_last_scan_time(self, channel_id: int) -> Optional[datetime]:
        """Get the last scan time for a channel."""
        channel_key = str(channel_id)
        if channel_key in self.history and self.history[channel_key].get('last_scan'):
            try:
                return datetime.fromisoformat(self.history[channel_key]['last_scan'])
            except:
                return None
        return None
    
    def add_scanned_urls(self, channel_id: int, urls: Set[str]):
        """Add scanned URLs to history for a channel."""
        channel_key = str(channel_id)
        if channel_key not in self.history:
            self.history[channel_key] = {
                'scanned_urls': [],
                'last_scan': None,
                'total_scans': 0
            }
        
        # Add new URLs to existing ones
        existing_urls = set(self.history[channel_key]['scanned_urls'])
        existing_urls.update(urls)
        self.history[channel_key]['scanned_urls'] = list(existing_urls)
        self.history[channel_key]['last_scan'] = datetime.now().isoformat()
        self.history[channel_key]['total_scans'] += 1
        
        self.save_history()
    
    def get_channel_stats(self, channel_id: int) -> Dict:
        """Get statistics for a channel."""
        channel_key = str(channel_id)
        if channel_key in self.history:
            return {
                'total_scanned': len(self.history[channel_key]['scanned_urls']),
                'last_scan': self.history[channel_key]['last_scan'],
                'total_scans': self.history[channel_key]['total_scans']
            }
        return {'total_scanned': 0, 'last_scan': None, 'total_scans': 0}
    
    def clear_channel_history(self, channel_id: int):
        """Clear scan history for a channel."""
        channel_key = str(channel_id)
        if channel_key in self.history:
            del self.history[channel_key]
            self.save_history()


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = ">"
        self.active_scans: Dict[int, bool] = {}  # Track active scans per channel
        self.scan_history = ScanHistory()  # History manager
        self.scan_recovery = ScanRecovery()  # Recovery manager

    async def on_ready(self):
        logger.info(f"[*] {self.user.name} is ALIVE!")
        logger.info(f"[*] Bot is in {len(self.guilds)} servers")
        print(f"🤖 Bot {self.user.name} đã sẵn sàng!")
        print(f"📊 Bot đang hoạt động trong {len(self.guilds)} servers")

    async def on_message(self, message):
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Check if message starts with prefix
        if not message.content.startswith(self.prefix):
            return
            
        command = message.content.removeprefix(self.prefix).strip()
        is_admin = message.author.guild_permissions.administrator if message.guild else True

        logger.info(f"[*] {format_date(datetime.now())}: {message.author}: {command}")

        # Ping command
        if command == "ping":
            await self.handle_ping(message)
            
        # Scan command
        elif command.startswith("scan"):
            await self.handle_scan(message, command, is_admin)
        
        # Recovery commands
        elif command == "check_recovery":
            await self.handle_check_recovery(message, is_admin)
        
        elif command == "resume_scan":
            await self.handle_resume_scan(message, is_admin)
        
        elif command == "clear_recovery":
            await self.handle_clear_recovery(message, is_admin)
        
        # History command
        elif command == "history":
            await self.handle_history(message, is_admin)
        
        # Clear history command
        elif command == "clear_history":
            await self.handle_clear_history(message, is_admin)
            
        # Help command
        elif command == "help":
            await self.handle_help(message)

    async def handle_ping(self, message):
        """Handle ping command."""
        latency = round(self.latency * 1000, 2)
        await message.channel.send(f"🏓 Pong! Latency: {latency}ms")
        logger.info(f"[+] Latency: {latency} ms")

    async def handle_help(self, message):
        """Handle help command."""
        embed = discord.Embed(
            title="🤖 Media Scanner Bot",
            description="Bot để quét và tải xuống media từ các kênh Discord với tính năng lưu lịch sử và khôi phục.",
            color=0x00FF00
        )
        embed.add_field(
            name="Lệnh quét",
            value=f"`{self.prefix}scan [số]` - Quét N tin nhắn gần nhất (chỉ media mới)\n"
                  f"`{self.prefix}scan [số] --all` - Quét tất cả media kể cả đã quét\n"
                  f"`{self.prefix}scan --new` - Quét từ lần quét cuối đến hiện tại\n"
                  f"`{self.prefix}scan --new [số]` - Quét từ lần quét cuối (tối đa N tin nhắn)",
            inline=False
        )
        embed.add_field(
            name="Lệnh khôi phục",
            value=f"`{self.prefix}check_recovery` - Kiểm tra quá trình quét bị gián đoạn\n"
                  f"`{self.prefix}resume_scan` - Tiếp tục quét từ điểm bị gián đoạn\n"
                  f"`{self.prefix}clear_recovery` - Xóa dữ liệu khôi phục",
            inline=False
        )
        embed.add_field(
            name="Lệnh khác",
            value=f"`{self.prefix}ping` - Kiểm tra độ trễ bot\n"
                  f"`{self.prefix}history` - Xem lịch sử quét kênh\n"
                  f"`{self.prefix}clear_history` - Xóa lịch sử quét kênh\n"
                  f"`{self.prefix}help` - Hiển thị tin nhắn trợ giúp này",
            inline=False
        )
        embed.set_footer(text="Tạo bởi nghuy0901")
        
        await message.channel.send(embed=embed)

    async def handle_check_recovery(self, message, is_admin):
        """Handle check recovery command."""
        if not is_admin:
            await message.reply("❌ Đây là lệnh chỉ dành cho admin.", delete_after=10)
            return
        
        recovery_data = self.scan_recovery.get_interrupted_scan(message.channel.id)
        
        if not recovery_data:
            await message.channel.send("✅ Không có quá trình quét nào bị gián đoạn trong kênh này.", delete_after=10)
            return
        
        start_time = datetime.fromisoformat(recovery_data['start_time'])
        
        embed = discord.Embed(
            title="🔄 Quá trình quét bị gián đoạn",
            description="Phát hiện quá trình quét chưa hoàn thành",
            color=0xFF9900
        )
        embed.add_field(
            name="🕐 Thời gian bắt đầu",
            value=format_display_date(start_time),
            inline=True
        )
        embed.add_field(
            name="📊 Loại quét",
            value=recovery_data['scan_type'],
            inline=True
        )
        embed.add_field(
            name="📝 Tin nhắn đã xử lý",
            value=f"{recovery_data['processed_count']} tin nhắn",
            inline=True
        )
        embed.add_field(
            name="📁 Media đã tìm thấy",
            value=f"{recovery_data['found_media']} tệp",
            inline=True
        )
        embed.add_field(
            name="🎯 Hành động",
            value=f"Sử dụng `{self.prefix}resume_scan` để tiếp tục quét",
            inline=False
        )
        
        await message.channel.send(embed=embed)

    async def handle_resume_scan(self, message, is_admin):
        """Handle resume scan command."""
        if not is_admin:
            await message.reply("❌ Đây là lệnh chỉ dành cho admin.", delete_after=10)
            return

        recovery_data = self.scan_recovery.get_interrupted_scan(message.channel.id)
        
        if not recovery_data:
            await message.channel.send("❌ Không có quá trình quét nào để khôi phục.", delete_after=10)
            return

        # Check if there's already an active scan in this channel
        if self.active_scans.get(message.channel.id, False):
            await message.reply("⚠️ Đã có một quét đang hoạt động trong kênh này.", delete_after=10)
            return

        # Mark channel as having active scan
        self.active_scans[message.channel.id] = True

        try:
            await message.channel.send("🔄 Đang khôi phục và tiếp tục quá trình quét...")
            
            # Extract parameters from recovery data
            scan_params = recovery_data['scan_params']
            last_message_id = recovery_data.get('last_processed_message')
            
            # Resume scanning from where it left off
            await self.resume_scanning_process(message, recovery_data, last_message_id)
            
        except Exception as e:
            logger.error(f"[-] Error in resume scan: {str(e)}")
            await message.channel.send(f"❌ Đã xảy ra lỗi khi khôi phục quét: {str(e)}", delete_after=10)
        finally:
            # Remove active scan flag
            self.active_scans[message.channel.id] = False

    async def handle_clear_recovery(self, message, is_admin):
        """Handle clear recovery command."""
        if not is_admin:
            await message.reply("❌ Đây là lệnh chỉ dành cho admin.", delete_after=10)
            return
        
        self.scan_recovery.clear_recovery_data(message.channel.id)
        await message.channel.send("✅ Đã xóa dữ liệu khôi phục của kênh này.", delete_after=10)

    async def resume_scanning_process(self, message, recovery_data, last_message_id):
        """Resume scanning process from where it left off."""
        scan_params = recovery_data['scan_params']
        
        # Get previously scanned URLs
        scanned_urls = self.scan_history.get_scanned_urls(message.channel.id)
        
        # Determine how to continue scanning based on original scan type
        scan_type = recovery_data['scan_type']
        
        if scan_type == "time_based":
            # Continue time-based scan
            since_time = datetime.fromisoformat(scan_params['since_time'])
            limit = scan_params.get('limit')
            message_history = await self.get_messages_since_time(message.channel, since_time, limit, last_message_id)
        else:
            # Continue number-based scan
            remaining_limit = scan_params['limit'] - recovery_data['processed_count']
            if remaining_limit <= 0:
                await message.channel.send("✅ Quá trình quét đã hoàn thành trước đó.")
                self.scan_recovery.complete_scan_session(message.channel.id)
                return
            
            message_history = await self.get_messages_from_point(message.channel, last_message_id, remaining_limit)
        
        if not message_history:
            await message.channel.send("✅ Không có tin nhắn mới nào để tiếp tục quét.")
            self.scan_recovery.complete_scan_session(message.channel.id)
            return

        # Continue analyzing messages
        scan_all = scan_params.get('scan_all', False)
        images, videos, others, new_urls = await self.analyze_messages_with_recovery(
            message_history, scanned_urls, scan_all, message.channel.id, recovery_data['processed_count']
        )

        # Calculate sizes and send report
        total_image_size, total_video_size, total_other_size = await self.calculate_media_sizes(
            message_history, images, videos, others
        )

        # Send report
        await self.send_resume_report(message, images, videos, others, 
                                    total_image_size, total_video_size, total_other_size, 
                                    len(message_history), recovery_data)

        # Handle download options if media found
        if images or videos or others:
            await self.handle_download_options(message, images, videos, others,
                                             total_image_size, total_video_size, total_other_size)
            
            # Save new URLs to history
            if new_urls:
                self.scan_history.add_scanned_urls(message.channel.id, new_urls)
                logger.info(f"[+] Added {len(new_urls)} new URLs to history")

        # Mark scan as completed
        self.scan_recovery.complete_scan_session(message.channel.id)
        await message.channel.send("✅ Đã hoàn thành quá trình quét được khôi phục!", delete_after=10)

    async def get_messages_from_point(self, channel, last_message_id, limit):
        """Get messages continuing from a specific point."""
        messages = []
        found_start = last_message_id is None  # If no last message, start from beginning
        
        async for message in channel.history(limit=limit * 2):  # Get more to find starting point
            if not found_start:
                if message.id == last_message_id:
                    found_start = True
                continue
            
            messages.append(message)
            if len(messages) >= limit:
                break
        
        return messages

    async def get_messages_since_time(self, channel, since_time: datetime, limit: Optional[int] = None, last_message_id: Optional[int] = None):
        """Get messages from channel since a specific time, optionally starting from a specific message."""
        messages = []
        count = 0
        max_messages = limit or 500
        found_start = last_message_id is None
        
        async for message in channel.history(limit=max_messages * 2):
            if not found_start:
                if message.id == last_message_id:
                    found_start = True
                continue
            
            # Convert message timestamp to naive datetime for comparison
            message_time = message.created_at.replace(tzinfo=None)
            since_time_naive = since_time.replace(tzinfo=None) if since_time.tzinfo else since_time
            
            if message_time <= since_time_naive:
                break
                
            messages.append(message)
            count += 1
            
            if limit and count >= limit:
                break
        
        logger.info(f"[+] Found {len(messages)} messages to continue scanning")
        return messages

    async def analyze_messages_with_recovery(self, message_history, scanned_urls: Set[str], scan_all: bool, channel_id: int, start_counter: int):
        """Analyze messages with recovery tracking."""
        images = {}
        videos = {}
        others = {}
        new_urls = set()
        
        counter = start_counter + 1
        processed_count = start_counter
        found_media = 0
        
        for message in message_history:
            processed_count += 1
            
            if message.attachments and not message.author.bot:
                for attachment in message.attachments:
                    attachment_url = str(attachment.url)
                    
                    # Skip if already scanned (unless scanning all)
                    if not scan_all and attachment_url in scanned_urls:
                        logger.debug(f"[*] Skipping already scanned: {attachment_url}")
                        continue
                    
                    logger.debug(f"[*] {counter} - {message.author.name}: {attachment}")

                    file_extension = attachment.url.rsplit(".", maxsplit=1)[-1]
                    file_extension = file_extension.split("?")[0]  # Remove query parameters
                    
                    author = safe_string(str(message.author))
                    attachment_name = f"{counter:04d}_{format_date(message.created_at)}_{author}.{file_extension}"

                    # Add to new URLs set
                    new_urls.add(attachment_url)
                    found_media += 1

                    if is_image(attachment.url):
                        logger.debug(f"[*] Image detected: {attachment.url}")
                        images[attachment_url] = attachment_name
                    elif is_video(attachment.url):
                        logger.debug(f"[*] Video detected: {attachment.url}")
                        videos[attachment_url] = attachment_name
                    else:
                        logger.debug(f"[*] Other media detected: {attachment.url}")
                        others[attachment_url] = attachment_name

                    counter += 1
            
            # Update recovery progress every 10 messages
            if processed_count % 10 == 0:
                self.scan_recovery.update_scan_progress(channel_id, message.id, processed_count, found_media)

        # Final update
        self.scan_recovery.update_scan_progress(channel_id, message_history[-1].id if message_history else None, processed_count, found_media)

        logger.info(f"[+] Resumed scan found: {len(images)} images, {len(videos)} videos, {len(others)} others (new: {len(new_urls)})")
        return images, videos, others, new_urls

    async def calculate_media_sizes(self, message_history, images, videos, others):
        """Calculate total sizes for different media types."""
        total_image_size = 0
        total_video_size = 0
        total_other_size = 0

        for msg in message_history:
            if msg.attachments and not msg.author.bot:
                for attachment in msg.attachments:
                    if str(attachment.url) in images:
                        total_image_size += attachment.size
                    elif str(attachment.url) in videos:
                        total_video_size += attachment.size
                    elif str(attachment.url) in others:
                        total_other_size += attachment.size

        return total_image_size, total_video_size, total_other_size

    async def send_resume_report(self, message, images, videos, others, 
                               total_image_size, total_video_size, total_other_size, 
                               message_count, recovery_data):
        """Send report for resumed scan."""
        colors = [0xFF0000, 0xFFEE00, 0x40FF00, 0x00BBFF, 0xFF00BB]
        
        embed_message = discord.Embed(
            title="📊 Báo cáo quét (Đã khôi phục)", 
            color=random.choice(colors)
        )
        
        embed_message.add_field(
            name="🔄 Tin nhắn tiếp tục quét",
            value=f"{message_count} tin nhắn",
            inline=True
        )
        
        embed_message.add_field(
            name="📝 Tổng tin nhắn đã xử lý",
            value=f"{recovery_data['processed_count'] + message_count} tin nhắn",
            inline=True
        )

        if images:
            media_size = convert_byte_to_mb(total_image_size)
            embed_message.add_field(
                name="🖼️ Hình ảnh",
                value=f"{len(images)} tệp ({media_size} MB)",
                inline=True
            )

        if videos:
            media_size = convert_byte_to_mb(total_video_size)
            embed_message.add_field(
                name="🎥 Video",
                value=f"{len(videos)} tệp ({media_size} MB)",
                inline=True
            )

        if others:
            media_size = convert_byte_to_mb(total_other_size)
            embed_message.add_field(
                name="📁 Media khác",
                value=f"{len(others)} tệp ({media_size} MB)",
                inline=True
            )

        total_media_size = total_image_size + total_video_size + total_other_size
        if total_media_size > 0:
            embed_message.add_field(
                name="💾 Tổng dung lượng",
                value=f"{convert_byte_to_mb(total_media_size)} MB",
                inline=True
            )

        embed_message.set_footer(text=f"Khôi phục bởi {message.author.display_name}")
        await message.channel.send(embed=embed_message)

    async def handle_history(self, message, is_admin):
        """Handle history command."""
        if not is_admin:
            await message.reply("❌ Đây là lệnh chỉ dành cho admin.", delete_after=10)
            return
        
        stats = self.scan_history.get_channel_stats(message.channel.id)
        
        embed = discord.Embed(
            title="📊 Lịch sử quét kênh",
            color=0x0099FF
        )
        embed.add_field(
            name="📁 Tổng media đã quét",
            value=f"{stats['total_scanned']} tệp",
            inline=True
        )
        embed.add_field(
            name="🔄 Số lần quét",
            value=f"{stats['total_scans']} lần",
            inline=True
        )
        
        if stats['last_scan']:
            last_scan = datetime.fromisoformat(stats['last_scan'])
            embed.add_field(
                name="⏰ Lần quét cuối",
                value=f"{format_display_date(last_scan)}",
                inline=False
            )
        else:
            embed.add_field(
                name="⏰ Lần quét cuối",
                value="Chưa có",
                inline=False
            )
        
        embed.set_footer(text=f"Kênh: {message.channel.name}")
        await message.channel.send(embed=embed)

    async def handle_clear_history(self, message, is_admin):
        """Handle clear history command."""
        if not is_admin:
            await message.reply("❌ Đây là lệnh chỉ dành cho admin.", delete_after=10)
            return
        
        self.scan_history.clear_channel_history(message.channel.id)
        await message.channel.send("✅ Đã xóa lịch sử quét của kênh này.", delete_after=10)

    async def handle_scan(self, message, command, is_admin):
        """Handle scan command."""
        if not is_admin:
            await message.reply("❌ Đây là lệnh chỉ dành cho admin.", delete_after=10)
            logger.info("[-] Unauthorized scan attempt")
            return

        # Check if there's already an active scan in this channel
        if self.active_scans.get(message.channel.id, False):
            await message.reply("⚠️ Đã có một quét đang hoạt động trong kênh này.", delete_after=10)
            return

        # Check for interrupted scan
        recovery_data = self.scan_recovery.get_interrupted_scan(message.channel.id)
        if recovery_data:
            await message.reply(f"⚠️ Có quá trình quét chưa hoàn thành. Sử dụng `{self.prefix}check_recovery` để kiểm tra hoặc `{self.prefix}resume_scan` để tiếp tục.", delete_after=15)
            return

        # Mark channel as having active scan
        self.active_scans[message.channel.id] = True

        try:
            # Parse command arguments
            command_parts = command.split()
            number_of_messages = None
            scan_all = False
            scan_from_last = False
            
            for part in command_parts[1:]:
                if part.isdigit():
                    number_of_messages = min(int(part), 500)
                elif part == "--all":
                    scan_all = True
                elif part == "--new":
                    scan_from_last = True

            # If no specific mode and no number, default to 5 messages with new only
            if not scan_all and not scan_from_last and number_of_messages is None:
                number_of_messages = 5

            # Start recovery session
            scan_type = "time_based" if scan_from_last else "number_based"
            scan_params = {
                'limit': number_of_messages,
                'scan_all': scan_all,
            }
            
            if scan_from_last:
                last_scan_time = self.scan_history.get_last_scan_time(message.channel.id)
                if not last_scan_time:
                    await message.channel.send("❌ Chưa có lịch sử quét trước đó. Sử dụng `>scan [số]` để quét lần đầu.", delete_after=15)
                    return
                scan_params['since_time'] = last_scan_time.isoformat()

            self.scan_recovery.start_scan_session(message.channel.id, scan_type, datetime.now(), scan_params)

            # Continue with regular scanning process
            await self.perform_scan(message, number_of_messages, scan_all, scan_from_last)

        except Exception as e:
            logger.error(f"[-] Error in scan command: {str(e)}")
            await message.channel.send(f"❌ Đã xảy ra lỗi khi quét: {str(e)}", delete_after=10)
        finally:
            # Remove active scan flag
            self.active_scans[message.channel.id] = False

    async def perform_scan(self, message, number_of_messages, scan_all, scan_from_last):
        """Perform the actual scanning process."""
        # Get last scan time for time-based scanning
        last_scan_time = None
        if scan_from_last:
            last_scan_time = self.scan_history.get_last_scan_time(message.channel.id)

        logger.info(f"[*] Scanning in {message.channel.name}, mode: all={scan_all}, from_last={scan_from_last}, limit={number_of_messages}")

        # Get previously scanned URLs if not scanning all
        scanned_urls = set()
        if not scan_all:
            scanned_urls = self.scan_history.get_scanned_urls(message.channel.id)

        # Show scanning status
        if scan_from_last:
            scan_description = f"từ {format_display_date(last_scan_time)} đến hiện tại"
            if number_of_messages:
                scan_description += f" (tối đa {number_of_messages} tin nhắn)"
        else:
            scan_mode = "tất cả media" if scan_all else "media mới"
            scan_description = f"{number_of_messages} tin nhắn gần nhất ({scan_mode})"

        status_msg = await message.channel.send(f"🔍 Đang quét {scan_description}...")

        # Get message history based on scan mode
        if scan_from_last:
            message_history = await self.get_messages_since_time(message.channel, last_scan_time, number_of_messages)
        else:
            message_history = [msg async for msg in message.channel.history(limit=number_of_messages)]

        if not message_history:
            await status_msg.edit(content="📭 Không có tin nhắn mới nào để quét.", delete_after=10)
            self.scan_recovery.complete_scan_session(message.channel.id)
            return

        # Analyze messages with recovery tracking
        images, videos, others, new_urls = await self.analyze_messages_with_recovery(
            message_history, scanned_urls, scan_all, message.channel.id, 0
        )

        # Calculate sizes
        total_image_size, total_video_size, total_other_size = await self.calculate_media_sizes(
            message_history, images, videos, others
        )

        # Update status message with results
        await status_msg.delete()
        
        # Send report
        await self.send_report(message, images, videos, others, 
                             total_image_size, total_video_size, total_other_size, 
                             len(message_history), scan_all, len(scanned_urls), scan_from_last, last_scan_time)

        # Handle download options if media found
        if images or videos or others:
            await self.handle_download_options(message, images, videos, others,
                                             total_image_size, total_video_size, total_other_size)
            
            # Save new URLs to history (only if there are new URLs)
            if new_urls:
                self.scan_history.add_scanned_urls(message.channel.id, new_urls)
                logger.info(f"[+] Added {len(new_urls)} new URLs to history")
        else:
            if scan_from_last:
                no_media_msg = "📭 Không tìm thấy media mới nào từ lần quét cuối."
            else:
                no_media_msg = "📭 Không tìm thấy media mới nào." if not scan_all else "📭 Không tìm thấy media nào trong các tin nhắn đã quét."
            await message.channel.send(no_media_msg, delete_after=10)

        # Mark scan as completed
        self.scan_recovery.complete_scan_session(message.channel.id)

    async def analyze_messages(self, message_history, scanned_urls: Set[str], scan_all: bool):
        """Analyze messages and categorize attachments."""
        return await self.analyze_messages_with_recovery(message_history, scanned_urls, scan_all, None, 0)

    async def send_report(self, message, images, videos, others, 
                         total_image_size, total_video_size, total_other_size, message_count, 
                         scan_all, previously_scanned, scan_from_last=False, last_scan_time=None):
        """Send scan report embed."""
        colors = [0xFF0000, 0xFFEE00, 0x40FF00, 0x00BBFF, 0xFF00BB]
        
        if scan_from_last:
            scan_mode = f"📊 Báo cáo quét (Từ {format_display_date(last_scan_time)})"
        elif scan_all:
            scan_mode = "📊 Báo cáo quét (Tất cả)"
        else:
            scan_mode = "📊 Báo cáo quét (Media mới)"
            
        embed_message = discord.Embed(title=scan_mode, color=random.choice(colors))
        
        embed_message.add_field(
            name="📝 Tin nhắn đã quét",
            value=f"{message_count} tin nhắn",
            inline=True
        )

        if not scan_all and not scan_from_last and previously_scanned > 0:
            embed_message.add_field(
                name="🗃️ Media đã quét trước đó",
                value=f"{previously_scanned} tệp",
                inline=True
            )

        if images:
            media_size = convert_byte_to_mb(total_image_size)
            embed_message.add_field(
                name="🖼️ Hình ảnh",
                value=f"{len(images)} tệp ({media_size} MB)",
                inline=True
            )

        if videos:
            media_size = convert_byte_to_mb(total_video_size)
            embed_message.add_field(
                name="🎥 Video",
                value=f"{len(videos)} tệp ({media_size} MB)",
                inline=True
            )

        if others:
            media_size = convert_byte_to_mb(total_other_size)
            embed_message.add_field(
                name="📁 Media khác",
                value=f"{len(others)} tệp ({media_size} MB)",
                inline=True
            )

        total_media_size = total_image_size + total_video_size + total_other_size
        if total_media_size > 0:
            embed_message.add_field(
                name="💾 Tổng dung lượng",
                value=f"{convert_byte_to_mb(total_media_size)} MB",
                inline=True
            )

        embed_message.set_footer(text=f"Yêu cầu bởi {message.author.display_name}")
        await message.channel.send(embed=embed_message)

    async def handle_download_options(self, message, images, videos, others,
                                    total_image_size, total_video_size, total_other_size):
        """Handle download options selection."""
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        options = []

        if total_image_size > 0:
            options.append("Hình ảnh")
        if total_video_size > 0:
            options.append("Video")
        if total_other_size > 0:
            options.append("Media khác")
        if len(options) > 1:
            options.append("Tất cả")

        if not options:
            return

        # Create options message
        options_text = "**📥 Tùy chọn tải xuống**\n"
        for i, option in enumerate(options):
            options_text += f"{emojis[i]} **{option}**\n"

        options_message = await message.channel.send(options_text)

        # Add reactions
        for i in range(len(options)):
            await options_message.add_reaction(emojis[i])

        options_emojis = [emojis[i] for i in range(len(options))]

        # Wait for user reaction
        emoji = await self.react_message(message, options_message, options_emojis)

        if not emoji:
            await options_message.edit(content="⏰ Yêu cầu tải xuống đã hết thời gian.", delete_after=10)
            return

        # Process download
        selection = options[options_emojis.index(emoji)]
        await self.process_download(options_message, selection, images, videos, others)

    async def process_download(self, options_message, selection, images, videos, others):
        """Process the actual download."""
        try:
            status_message = await options_message.edit(content=f"⬬ Đang tải xuống {selection}...")

            # Create download folder
            server_name = options_message.guild.name if options_message.guild else "DirectMessage"
            channel_name = options_message.channel.name if hasattr(options_message.channel, 'name') else "DirectMessage"
            folder = create_folder(server_name=server_name, channel_name=channel_name)

            # Download based on selection
            download_tasks = []
            total_files = 0

            if selection == "Hình ảnh" or selection == "Tất cả":
                for url, name in images.items():
                    download_tasks.append(download_media(url, folder, name))
                total_files += len(images)

            if selection == "Video" or selection == "Tất cả":
                for url, name in videos.items():
                    download_tasks.append(download_media(url, folder, name))
                total_files += len(videos)

            if selection == "Media khác" or selection == "Tất cả":
                for url, name in others.items():
                    download_tasks.append(download_media(url, folder, name))
                total_files += len(others)

            # Execute downloads
            if download_tasks:
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
                successful = sum(1 for result in results if result is True)
                
                if successful == total_files:
                    await status_message.edit(
                        content=f"✅ Tải xuống hoàn tất! {successful}/{total_files} tệp đã được tải xuống thành công.\n"
                               f"📁 Đã lưu vào: `{folder}`",
                        delete_after=30
                    )
                else:
                    await status_message.edit(
                        content=f"⚠️ Tải xuống hoàn tất một phần. {successful}/{total_files} tệp đã được tải xuống.\n"
                               f"📁 Đã lưu vào: `{folder}`",
                        delete_after=30
                    )
            else:
                await status_message.edit(content="❌ Không có tệp nào để tải xuống.", delete_after=10)

        except Exception as e:
            logger.error(f"[-] Error during download: {str(e)}")
            await options_message.edit(content=f"❌ Tải xuống thất bại: {str(e)}", delete_after=10)

    async def react_message(self, command_message: discord.Message, 
                          options_message: discord.Message, options_emojis: list[str]) -> Optional[str]:
        """Wait for user reaction and return the selected emoji."""
        def check(reaction, user):
            logger.debug(f"Reaction check: message_id={reaction.message.id}, "
                        f"expected={options_message.id}, user={user}, "
                        f"author={command_message.author}, emoji={reaction.emoji}")
            return (
                reaction.message.id == options_message.id
                and user == command_message.author
                and str(reaction.emoji) in options_emojis
            )

        logger.info(f"[*] Waiting for reaction on message {options_message.id} from user {command_message.author}")

        try:
            reaction, *_ = await self.wait_for("reaction_add", timeout=60.0, check=check)
            logger.info(f"[+] Received valid reaction: {reaction.emoji}")
            return str(reaction.emoji)
        except asyncio.TimeoutError:
            logger.info("[-] User didn't react in time.")
            return None


def main():
    """Main function to run the bot."""
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your_actual_bot_token_here":
        logger.error("[-] Vui lòng thay thế DISCORD_TOKEN bằng token thực của bot!")
        print("❌ Lỗi: Vui lòng thay thế DISCORD_TOKEN bằng token thực của bot!")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    
    client = MyClient(intents=intents)
    
    try:
        print("🚀 Đang khởi động bot...")
        client.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("[-] Token Discord không hợp lệ!")
        print("❌ Token Discord không hợp lệ!")
    except Exception as e:
        logger.error(f"[-] Lỗi khi chạy bot: {str(e)}")
        print(f"❌ Lỗi khi chạy bot: {str(e)}")


if __name__ == "__main__":
    main()