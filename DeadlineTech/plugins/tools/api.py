from pyrogram import Client, filters
from pyrogram.types import Message

from DeadlineTech.platforms.Youtube import get_stream_stats
from DeadlineTech import app
from DeadlineTech.misc import SUDOERS

AUTHORIZED_USERS = [7321657753]

@app.on_message(filters.command("yt"))
async def stream_stats_handler(client: Client, message: Message):
    
    if AUTHORIZED_USERS and message.from_user.id not in AUTHORIZED_USERS:
        return await message.reply("🚫 You are not authorized to use this command.")

    try:
        stats = get_stream_stats()
        await message.reply_text(stats)
    except Exception as e:
        await message.reply(f"❌ Failed to fetch stream stats.\n\nError: {e}")
