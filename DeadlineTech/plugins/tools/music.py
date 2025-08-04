# 🎿 DeadlineTech Music Bot (Enhanced with Logging & Thumbnails + File Cache)

import os
import re
import asyncio
import requests
import logging
import urllib.request
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction
from youtubesearchpython.__future__ import VideosSearch
from config import API_KEY, SAVE_CHANNEL_ID
from DeadlineTech import app
from DeadlineTech.db import get_saved_file_id, mark_song_as_sent, is_song_sent

# 📄 Logging Setup
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "music_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

MIN_FILE_SIZE = 51200
API_URL = "https://deadlineTech.site"
DOWNLOADS_DIR = "downloads"

# 🔽 Extract video ID from various YouTube link formats
def extract_video_id(link: str) -> str | None:
    patterns = [
        r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:playlist\?list=[^&]+&v=|v\/)([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:.*\?v=|.*/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    return None

# 🔽 Download thumbnail

def download_thumbnail(video_id: str) -> str | None:
    thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    thumb_path = os.path.join(DOWNLOADS_DIR, f"{video_id}.jpg")
    try:
        urllib.request.urlretrieve(thumb_url, thumb_path)
        return thumb_path
    except Exception as e:
        logger.warning(f"Thumbnail download failed: {e}")
        return None

# 🔽 Download audio using external API
def api_dl(video_id: str) -> str | None:
    api_url = f"{API_URL}/download/song/{video_id}?key={API_KEY}"
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOADS_DIR, f"{video_id}.mp3")
    if os.path.exists(file_path):
        logger.info(f"File already exists: {file_path}")
        return file_path
    try:
        logger.info(f"Requesting song from API: {api_url}")
        response = requests.get(api_url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(file_path) < MIN_FILE_SIZE:
                os.remove(file_path)
                logger.warning(f"File too small, deleted: {file_path}")
                return None
            logger.info(f"Downloaded file saved at: {file_path}")
            return file_path
        logger.warning(f"Failed API response: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"API Download error: {e}")
        return None

async def remove_file_later(path: str, delay: int = 600):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"🗑️ Deleted file: {path}")
    except Exception as e:
        logger.error(f"❌ File deletion error: {e}")

async def delete_message_later(client: Client, chat_id: int, message_id: int, delay: int = 600):
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        logger.info(f"🗑️ Deleted message: {message_id}")
    except Exception as e:
        logger.error(f"❌ Message deletion error: {e}")

def parse_duration(duration: str) -> int:
    parts = list(map(int, duration.split(":")))
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m = 0, parts[0]
        s = parts[1]
    else:
        return int(parts[0])
    return h * 3600 + m * 60 + s

@app.on_message(filters.command(["song", "music"]))
async def song_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "🎿 <b>How to use:</b>\nSend <code>/music [song name or YouTube link]</code>")

    query = message.text.split(None, 1)[1].strip()
    logger.info(f"Received /music command: {query}")
    video_id = extract_video_id(query)

    if video_id:
        await message.reply_text("🎼 <i>Fetching your track...</i>")
        await send_audio_by_video_id(client, message, video_id)
    else:
        await message.reply_text("🔍 <i>Searching YouTube for your song...</i>")
        try:
            videos_search = VideosSearch(query, limit=5)
            results = (await videos_search.next()).get('result', [])
            if not results:
                return await message.reply_text("❌ <b>No results found.</b> Try a different query.")

            buttons = [[
                InlineKeyboardButton(
                    text=f"🎵 {video['title'][:30]}{'...' if len(video['title']) > 30 else ''}",
                    callback_data=f"dl_{video['id']}"
                )
            ] for video in results]

            await message.reply_text(
                "🎶 <b>Select the song to download:</b>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            logger.error(f"Error during YouTube search: {e}")
            await message.reply_text(f"⚠️ <b>Error during search:</b> {e}")

@app.on_callback_query(filters.regex(r"^dl_(.+)$"))
async def download_callback(client: Client, cq: CallbackQuery):
    video_id = cq.data.split("_", 1)[1]
    logger.info(f"Download selected via button: {video_id}")
    await cq.answer("🎿 Starting download...")
    await client.send_chat_action(cq.message.chat.id, ChatAction.UPLOAD_AUDIO)
    await cq.message.edit("⏳ <i>Downloading and processing audio...</i>")
    await send_audio_by_video_id(client, cq.message, video_id)
    await cq.message.edit("✅ <b>Done!</b> Send /music to get more music 🎵")

async def send_audio_by_video_id(client: Client, message: Message, video_id: str):
    try:
        videos_search = VideosSearch(video_id, limit=1)
        result = (await videos_search.next())['result'][0]
        title = result.get('title', "Unknown Title")
        duration_str = result.get('duration', '0:00')
        duration = parse_duration(duration_str)
        video_url = result.get('link')
        logger.info(f"Preparing song: {title} ({video_id})")
    except Exception as e:
        logger.warning(f"Failed to fetch metadata: {e}")
        title, duration_str, duration, video_url = "Unknown Title", "0:00", 0, None

    thumb_path = await asyncio.to_thread(download_thumbnail, video_id)

    # ✅ Use saved file_id if exists
    existing_file_id = get_saved_file_id(video_id)
    if existing_file_id:
        audio_msg = await message.reply_audio(
            audio=existing_file_id,
            title=title,
            performer="DeadlineTech",
            duration=duration,
            caption=f"🎿 <b>{title}</b>\n🕒 <b>Duration:</b> {duration_str}\n🔗 <a href=\"{video_url}\">Watch on YouTube</a>\n\n🎶 Requested by: <b>{message.from_user.first_name}</b>\n⚡ <i>Enjoy your track with</i> <a href=\"https://t.me/DeadlineTechTeam\">DeadlineTech</a>",
            thumb=thumb_path if thumb_path else None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎧 Get Your Music", url="https://t.me/DeadlineTechMusic")]
            ])
        )
        logger.info(f"🪄 Sent from cache: {video_id}")
        return

    file_path = await asyncio.to_thread(api_dl, video_id)
    if not file_path:
        return await message.reply_text("❌ <b>Failed to download the song.</b>")

    audio_msg = await message.reply_audio(
        audio=file_path,
        title=title,
        performer="DeadlineTech",
        duration=duration,
        caption=f"🎿 <b>{title}</b>\n🕒 <b>Duration:</b> {duration_str}\n🔗 <a href=\"{video_url}\">Watch on YouTube</a>\n\n🎶 Requested by: <b>{message.from_user.first_name}</b>\n⚡ <i>Enjoy your track with</i> <a href=\"https://t.me/DeadlineTechTeam\">DeadlineTech</a>",
        thumb=thumb_path if thumb_path else None,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎧 Get Your Music", url="https://t.me/DeadlineTechMusic")]
        ])
    )

    if not is_song_sent(video_id) and SAVE_CHANNEL_ID:
        try:
            sent = await client.send_audio(
                chat_id=SAVE_CHANNEL_ID,
                audio=file_path,
                title=title,
                performer="DeadlineTech",
                duration=duration,
                caption=f"🎼 <b>{title}</b>\n🕒 Duration: {duration_str}\n📱 Source: <a href=\"{video_url}\">YouTube</a>\n🔊 Delivered by: <a href=\"https://t.me/DeadlineTechTeam\">DeadlineTech Music Bot</a>",
                thumb=thumb_path if thumb_path else None
            ) 
            mark_song_as_sent(video_id, sent.audio.file_id)
            logger.info(f"✅ Saved to channel and cached: {SAVE_CHANNEL_ID}")
        except Exception as e:
            logger.error(f"❌ Error saving to channel: {e}")

    if thumb_path:
        asyncio.create_task(remove_file_later(thumb_path))
    asyncio.create_task(remove_file_later(file_path))
    asyncio.create_task(delete_message_later(client, message.chat.id, audio_msg.id))

