import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from DeadlineTech import app
from config import LOGGER_ID as JOINLOGS

# NEW: add this in your config.py and import it here:
# ALERT_USER_IDS = [6848223695, 89891145, 7448958077]
# fallback if not provided

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Cache the bot's ID at startup
JOINLOG = -1003499984720
BOT_ID = None


async def _ensure_bot_id(client: Client):
    global BOT_ID
    if BOT_ID is None:
        try:
            bot_user = await client.get_me()
            BOT_ID = bot_user.id
            logger.info(f"Cached bot ID: {BOT_ID}")
        except Exception:
            logger.exception("Failed to get bot info")
            return False
    return True


def _chat_meta(message: Message):
    chat_title = message.chat.title
    chat_id = message.chat.id
    chat_username = f"@{message.chat.username}" if message.chat.username else "Private Group"
    chat_link = f"https://t.me/{message.chat.username}" if message.chat.username else None
    return chat_title, chat_id, chat_username, chat_link


def _actor_html(user):
    if not user:
        return "Unknown User"
    first = (user.first_name or "User").replace("<", "&lt;").replace(">", "&gt;")
    return f"<a href='tg://user?id={user.id}'>👤{first}</a>"


async def _notify_alerts(client: Client, text: str):
    """DM the configured owners/admins when critical events happen (like self-leave)."""
    if not ALERT_USER_IDS:
        logger.warning("ALERT_USER_IDS is empty; no one will be DM'd for self-leave.")
        return
    for uid in ALERT_USER_IDS[:3]:  # ensure only 3 DMs as requested
        try:
            await client.send_message(uid, text, disable_web_page_preview=True)
        except Exception:
            logger.exception(f"Failed to send alert DM to {uid}")


@app.on_message(filters.new_chat_members)
async def on_new_chat_members(client: Client, message: Message):
    if not await _ensure_bot_id(client):
        return

    for new_member in message.new_chat_members:
        if new_member.id == BOT_ID:
            try:
                added_by = _actor_html(message.from_user) if message.from_user else "Unknown User"
                chat_title, chat_id, chat_username, chat_link = _chat_meta(message)

                log_text = (
                    "<b>🚀 Bot Added Successfully!</b>\n\n"
                    "╭───────⍟\n"
                    f"├ 💬 <b>Chat Name:</b> <code>{chat_title}</code>\n"
                    f"├ 🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
                    f"├ 🌐 <b>Username:</b> {chat_username}\n"
                    f"└ 👤 <b>Added By:</b> {added_by}\n"
                    "╰─────────────⍟"
                )
                buttons = [[InlineKeyboardButton("➤ Link 🔗", url=chat_link)]] if chat_link else None

                await client.send_message(
                    JOINLOGS,
                    text=log_text,
                    reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
                    disable_web_page_preview=True
                )
                logger.info(f"Join log sent for chat ID: {chat_id}")
            except Exception:
                logger.exception(f"[JOINLOG ERROR] Failed to send join log for chat ID: {message.chat.id}")


@app.on_message(filters.left_chat_member)
async def on_left_chat_member(client: Client, message: Message):
    """
    Fires when someone leaves or is removed.
    - If it's the bot itself (left_user.id == BOT_ID), we log it.
    - If actor == bot (self-leave), we additionally DM 3 owners with a 'hacked' alert.
    """
    if not await _ensure_bot_id(client):
        return

    try:
        left_user = message.left_chat_member
        if not left_user or left_user.id != BOT_ID:
            return  # Not our bot; ignore

        actor = message.from_user
        is_self_leave = bool(actor and actor.id == BOT_ID)

        chat_title, chat_id, chat_username, chat_link = _chat_meta(message)

        if is_self_leave:
            header = "🚨 <b>Bot Left the Chat by Itself</b>\n\n"
            cause_line = "└ 🔎 <b>Reason:</b> Self-leave detected (actor is the bot)\n"
        else:
            if actor:
                header = "<b>🚪 Bot Removed from Chat</b>\n\n"
                cause_line = f"└ 🧹 <b>Removed By:</b> {_actor_html(actor)}\n"
            else:
                header = "<b>🚪 Bot Left the Chat</b>\n\n"
                cause_line = "└ 🧭 <b>Reason:</b> Left or removed (no actor info)\n"

        log_text = (
            f"{header}"
            "╭───────⍟\n"
            f"├ 💬 <b>Chat Name:</b> <code>{chat_title}</code>\n"
            f"├ 🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"├ 🌐 <b>Username:</b> {chat_username}\n"
            f"{cause_line}"
            "╰─────────────⍟"
        )
        buttons = [[InlineKeyboardButton("➤ Link 🔗", url=chat_link)]] if chat_link else None

        # Send to logger group
        await client.send_message(
            JOINLOG,
            text=log_text,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            disable_web_page_preview=True
        )
        logger.info(f"Left log sent for chat ID: {chat_id}")

        # If bot left by itself, DM 3 users with a strong warning
        if is_self_leave:
            dm_text = (
                "⚠️ <b>Security Alert</b>\n\n"
                "The bot <b>left a chat by itself</b>.\n"
                "This may indicate the bot is compromised or malfunctioning.\n\n"
                "✅ Recommended actions:\n"
                "• Revoke API keys / session strings immediately\n"
                "• Rotate tokens and regenerate secrets\n"
                "• Review recent logs & deployments\n"
                "• Re-add the bot only after securing credentials\n\n"
                f"📍 <b>Chat:</b> <code>{chat_title}</code>\n"
                f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>"
            )
            await _notify_alerts(client, dm_text)

    except Exception:
        logger.exception(f"[LEFTLOG ERROR] Failed to send left log for chat ID: {getattr(message.chat, 'id', 'unknown')}")
