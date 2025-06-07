from pyrogram import filters
from pyrogram.types import Message

from DeadlineTech import app
from DeadlineTech.misc import SUDOERS
from DeadlineTech.utils.database import get_client, is_active_chat
from config import LOGGER_ID
from pyrogram.enums import ChatType

@app.on_message(filters.command("cleanassistants") & SUDOERS)
async def clean_assistants_command(client, message: Message):
    from DeadlineTech.core.userbot import assistants

    msg = await message.reply_text("🧹 Cleaning inactive chats... Please wait.")
    total_left = 0

    for num in assistants:
        try:
            client = await get_client(num)
            left = 0
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                if chat.type in [ChatType.SUPERGROUP, ChatType.GROUP, ChatType.CHANNEL]:
                    if chat.id in [LOGGER_ID, -1001686672798, -1001549206010]:  # Excluded chats
                        continue
                    if not await is_active_chat(chat.id):
                        try:
                            await client.leave_chat(chat.id)
                            left += 1
                        except Exception as e:
                            print(f"[CleanAssistant Error] Failed to leave {chat.title} ({chat.id}): {e}")
            total_left += left
        except Exception as e:
            print(f"[CleanAssistant Error] Assistant {num} failed: {e}")

    await msg.edit_text(f"✅ Cleaned assistants.\nTotal chats left: <b>{total_left}</b>.")
