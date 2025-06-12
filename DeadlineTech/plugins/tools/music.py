import os
import re
import asyncio
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction
from youtubesearchpython.__future__ import VideosSearch, Playlist

from DeadlineTech import app
from config import API_KEY, API_BASE_URL, SAVE_CHANNEL_ID
from DeadlineTech.db import is_song_sent, mark_song_as_sent

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


def extract_playlist_id(link: str) -> str | None:
    match = re.search(r"(?:list=)([a-zA-Z0-9_-]+)", link)
    return match.group(1) if match else None


def api_dl(video_id: str) -> str | None:
    api_url = f"{API_BASE_URL}/download/song/{video_id}?key={API_KEY}"
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOADS_DIR, f"{video_id}.mp3")

    if os.path.exists(file_path):
        return file_path

    try:
        response = requests.get(api_url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(file_path) < MIN_FILE_SIZE:
                os.remove(file_path)
                return None
            return file_path
        return None
    except Exception as e:
        print(f"API Download error: {e}")
        return None


async def remove_file_later(path: str, delay: int = 600):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"🗑️ Deleted file: {path}")
    except Exception as e:
        print(f"❌ File deletion error: {e}")


async def delete_message_later(client: Client, chat_id: int, message_id: int, delay: int = 600):
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        print(f"🗑️ Deleted message: {message_id}")
    except Exception as e:
        print(f"❌ Message deletion error: {e}")


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
        return await message.reply_text("🎧 <b>Usage:</b> <code>/song &lt;YouTube URL or Song Name&gt;</code>")

    query = message.text.split(None, 1)[1].strip()
    playlist_id = extract_playlist_id(query)
    if playlist_id:
        await message.reply_text("📃 <i>Fetching playlist...</i>")
        return await handle_playlist(client, message, playlist_id)

    video_id = extract_video_id(query)
    if video_id:
        m = await message.reply("🎼 Fetching your song...")
        await send_audio_by_video_id(client, message, video_id, m)
    else:
        m = await message.reply("🔍 Searching...")
        try:
            videos_search = VideosSearch(query, limit=5)
            results = (await videos_search.next()).get('result', [])
            if not results:
                return await m.edit("❌ No results found.")

            buttons = [[
                InlineKeyboardButton(
                    text=(video['title'][:30] + '...') if len(video['title']) > 30 else video['title'],
                    callback_data=f"dl_{video['id']}"
                )
            ] for video in results]

            await m.edit("🎶 <b>Select a song from the results below:</b>", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            await m.edit(f"❌ Search error: {e}")


@app.on_callback_query(filters.regex(r"^dl_(.+)$"))
async def download_callback(client: Client, cq: CallbackQuery):
    video_id = cq.data.split("_", 1)[1]
    await cq.answer("🎧 Downloading your track...", show_alert=False)
    await client.send_chat_action(cq.message.chat.id, ChatAction.UPLOAD_AUDIO)
    await cq.message.edit("🎶 Getting your audio ready...")
    await send_audio_by_video_id(client, cq.message, video_id, cq.message)
    await cq.message.edit("✅ All done! 🎶 Grab more at:- @DeadlineTechMusic 🎧")


async def handle_playlist(client: Client, message: Message, playlist_id: str):
    try:
        pl = Playlist(f"https://www.youtube.com/playlist?list={playlist_id}")
        data = await pl.next()
        videos = data.get("videos", [])[:5]
        if not videos:
            return await message.reply_text("❌ No videos found in playlist.")

        await message.reply_text(f"🎶 <b>Found {len(videos)} tracks in the playlist.</b>\n🎧 Downloading top 5 now...")
        for video in videos:
            await send_audio_by_video_id(client, message, video["id"], message)
            await asyncio.sleep(1)
    except Exception as e:
        return await message.reply_text(f"❌ Playlist error: {e}")


async def send_audio_by_video_id(client: Client, message: Message, video_id: str, status_message: Message):
    try:
        videos_search = VideosSearch(video_id, limit=1)
        result = (await videos_search.next())['result'][0]
        title = result.get('title', "Unknown Title")
        duration_str = result.get('duration', '0:00')
        duration = parse_duration(duration_str)
        video_url = result.get('link')
        thumbnail_url = result.get("thumbnails", [{}])[0].get("url")
    except Exception:
        title, duration_str, duration, video_url, thumbnail_url = "Unknown Title", "0:00", 0, None, None

    thumb_path = None
    if thumbnail_url:
        thumb_path = os.path.join(DOWNLOADS_DIR, f"{video_id}.jpg")
        try:
            thumb_response = requests.get(thumbnail_url, timeout=10)
            if thumb_response.status_code == 200:
                with open(thumb_path, "wb") as f:
                    f.write(thumb_response.content)
        except Exception as e:
            print(f"⚠️ Failed to fetch thumbnail: {e}")
            thumb_path = None

    file_path = await asyncio.to_thread(api_dl, video_id)
    if not file_path:
        return await status_message.edit("❌ Could not download this song.")

    caption = (
        f"🎧 <b>{title}</b>\n"
        f"🕒 Duration: <code>{duration_str}</code>\n"
        f"🔗 <a href=\"{video_url}\">Watch on YouTube</a>\n"
        f"📥 Saved in our music collection\n\n"
        f"💽 <i>Powered by</i> <a href='https://t.me/DeadlineTechTeam'>DeadlineTech</a>"
    )

    audio_msg = await message.reply_audio(
        audio=file_path,
        title=title,
        performer="DeadlineTech",
        duration=duration,
        caption=caption,
        thumb=thumb_path,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎼 More Music", url="https://t.me/DeadlineTechMusic")]
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
                caption=(
                    f"🎵 <b>{title}</b>\n"
                    f"🕒 Duration: <code>{duration_str}</code>\n"
                    f"🔗 <a href=\"{video_url}\">YouTube Link</a>\n"
                    f"🎶 Grab more: @DeadlineTechMusic\n\n"
                    f"💽 <i>Brought to you by</i> <a href='https://t.me/DeadlineTechTeam'>DeadlineTech</a>"
                ),
                thumb=thumb_path,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎧 Listen Here", url="https://t.me/DeadlineTechMusic")]
                ])
            )
            mark_song_as_sent(video_id)
        except Exception as e:
            print(f"❌ Error saving to channel: {e}")

    asyncio.create_task(remove_file_later(file_path))
    if thumb_path:
        asyncio.create_task(remove_file_later(thumb_path))
    asyncio.create_task(delete_message_later(client, message.chat.id, audio_msg.id))
