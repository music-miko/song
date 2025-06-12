from pyrogram import filters
from pyrogram.types import Message
from DeadlineTech import app  # assuming 'app' is your Pyrogram client
from DeadlineTech.platforms.Youtube import get_stats

OWNER_ID = 6848223695

@app.on_message(filters.command("api") & filters.user(OWNER_ID))
async def show_stats(_, message: Message):
    stats = await get_stats()
    await message.reply_text(f"<blockquote>{stats}</blockquote>")
