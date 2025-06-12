# 🎧 DeadlineTech Music Bot (Enhanced with Logging)

import os
import re
import asyncio
import requests
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction
from youtubesearchpython.__future__ import VideosSearch

from DeadlineTech import app
from config import API_KEY, API_BASE_URL, SAVE_CHANNEL_ID
from DeadlineTech.db import is_song_sent, mark_song_as_sent

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
DOWNLOADS_DIR = "downloads"

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

def api_dl(video_id: str) -> str | None:
    api_url = f"{API_BASE_URL}/download/song/{video_id}?key={API_KEY}"
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
            "🎧 <b>How to use:</b>
Send <code>/song [song name or YouTube link]</code>",
        )

    query = message.text.split(None, 1)[1].strip()
    logger.info(f"Received /song command: {query}")
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
    await cq.answer("🎧 Starting download...")
    await client.send_chat_action(cq.message.chat.id, ChatAction.UPLOAD_AUDIO)
    await cq.message.edit("⏳ <i>Downloading and processing audio...</i>")
    await send_audio_by_video_id(client, cq.message, video_id)
    await cq.message.edit("✅ <b>Done!</b> Send /song to get more music 🎵")

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

    file_path = await asyncio.to_thread(api_dl, video_id)
    if not file_path:
        return await message.reply_text("❌ <b>Failed to download the song.</b>")

    caption = (
        f"🎧 <b>{title}</b>
"
        f"🕒 <b>Duration:</b> {duration_str}
"
        f"🔗 <a href=\"{video_url}\">Watch on YouTube</a>

"
        f"🚀 <i>Powered by</i> <a href=\"https://t.me/DeadlineTechTeam\">DeadlineTech</a>"
    )

    audio_msg = await message.reply_audio(
        audio=file_path,
        title=title,
        performer="DeadlineTech",
        duration=duration,
        caption=caption,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎼 More Music", url="https://t.me/DeadlineTechMusic")],
        ])
    )

    if not is_song_sent(video_id) and SAVE_CHANNEL_ID:
        try:
            await client.send_audio(
                chat_id=SAVE_CHANNEL_ID,
                audio=file_path,
                title=title,
                performer="DeadlineTech",
                duration=duration,
                caption=caption,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Powered by", url="https://t.me/DeadlineTechTeam")]
                ])
            )
            mark_song_as_sent(video_id)
            logger.info(f"✅ Saved to channel: {SAVE_CHANNEL_ID}")
        except Exception as e:
            logger.error(f"❌ Error saving to channel: {e}")

    asyncio.create_task(remove_file_later(file_path))
    asyncio.create_task(delete_message_later(client, message.chat.id, audio_msg.id))
