from pyrogram import Client, filters
from pyrogram.types import Message
import config
from DeadlineTech import app
from DeadlineTech.misc import SUDOERS
import datetime


def get_stats_message_html():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg = f"📊 <b>Download Stats Summary</b>\n"
    msg += f"<i>As of {now}</i>\n\n"

    msg += "🎵 <b>Song Audio</b>\n"
    msg += f"  ├─ Requested: <code>{config.songaudio_requests}</code>\n"
    msg += f"  ├─ Success  : <code>{config.songaudio_success}</code>\n"
    msg += f"  └─ Failed   : <code>{config.songaudio_failed}</code>\n\n"

    msg += "📼 <b>Song Video</b>\n"
    msg += f"  ├─ Requested: <code>{config.songvideo_requests}</code>\n"
    msg += f"  ├─ Success  : <code>{config.songvideo_success}</code>\n"
    msg += f"  └─ Failed   : <code>{config.songvideo_failed}</code>\n\n"

    msg += "📺 <b>Video</b>\n"
    msg += f"  ├─ Requested: <code>{config.video_requests}</code>\n"
    msg += f"  ├─ Success  : <code>{config.video_success}</code>\n"
    msg += f"  └─ Failed   : <code>{config.video_failed}</code>\n\n"

    msg += "🔊 <b>Audio</b>\n"
    msg += f"  ├─ Requested: <code>{config.audio_requests}</code>\n"
    msg += f"  ├─ Success  : <code>{config.audio_success}</code>\n"
    msg += f"  └─ Failed   : <code>{config.audio_failed}</code>\n\n"

    return msg


# Pyrogram command handler for /stats
@Client.on_message(filters.command("yt") & SUDOERS)
async def stats_handler(client: Client, message: Message):
    html = get_stats_message_html()
    await message.reply_text(html)
