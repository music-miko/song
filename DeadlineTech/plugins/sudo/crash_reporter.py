# Powered by DeadlineTech
import logging
from pyrogram import Client, filters
from DeadlineTech import app
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ✅ Handle member joins, leaves, promotions, demotions
@app.on_chat_member_updated()
async def handle_member_update(client: Client, update: ChatMemberUpdated):
    user = update.from_user
    chat = update.chat
    old = update.old_chat_member
    new = update.new_chat_member

    # Safely handle cases where old/new is None
    if not old or not new:
        return

    if old.status != new.status:
        if new.status == ChatMemberStatus.MEMBER:
            logger.info(f"[JOIN] {user.first_name} ({user.id}) joined {chat.title} ({chat.id})")
        elif new.status == ChatMemberStatus.LEFT:
            logger.info(f"[LEAVE] {user.first_name} ({user.id}) left {chat.title} ({chat.id})")
        elif new.status == ChatMemberStatus.ADMINISTRATOR:
            logger.info(f"[PROMOTED] {user.first_name} ({user.id}) was promoted in {chat.title} ({chat.id})")
        elif old.status == ChatMemberStatus.ADMINISTRATOR and new.status != ChatMemberStatus.ADMINISTRATOR:
            logger.info(f"[DEMOTED] {user.first_name} ({user.id}) was demoted in {chat.title} ({chat.id})")


# ✅ Handle video chat started (includes voice chats)
@app.on_message(filters.video_chat_started)
async def video_chat_started_handler(client: Client, message: Message):
    chat = message.chat
    logger.info(f"[VC STARTED] Video chat started in {chat.title} ({chat.id})")


# ✅ Handle video chat ended
@app.on_message(filters.video_chat_ended)
async def video_chat_ended_handler(client: Client, message: Message):
    chat = message.chat
    logger.info(f"[VC ENDED] Video chat ended in {chat.title} ({chat.id})")


# ✅ Handle pinned messages
@app.on_message(filters.pinned_message)
async def pinned_message_handler(client: Client, message: Message):
    chat = message.chat
    pinned = message.pinned_message

    if pinned:
        logger.info(f"[PINNED] Message pinned in {chat.title} ({chat.id}) - Pinned Msg ID: {pinned.id}")
    else:
        logger.info(f"[PINNED] A message was pinned in {chat.title} ({chat.id}), but content is not accessible.")

