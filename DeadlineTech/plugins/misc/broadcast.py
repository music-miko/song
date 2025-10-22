import asyncio
import random
import logging
from pyrogram import filters
from pyrogram.errors import FloodWait, RPCError, Forbidden, PeerIdInvalid
from pyrogram.enums import ChatMembersFilter
from pyrogram.types import Message

from DeadlineTech import app
from DeadlineTech.misc import SUDOERS
from DeadlineTech.utils.database import (
    get_served_users,
    get_served_chats,
    get_active_chats,
    get_authuser_names,
)
from DeadlineTech.utils.formatters import alpha_to_int
from config import adminlist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
logger = logging.getLogger("Broadcast")

# Global semaphore — very low concurrency to reduce flood
SEMAPHORE = asyncio.Semaphore(3)


@app.on_message(filters.command("broadcast") & SUDOERS)
async def broadcast_command(_, message: Message):
    try:
        cmd = message.text.lower()
        mode = "forward" if "-forward" in cmd else "copy"

        # Determine recipients
        if "-all" in cmd:
            users = [u["user_id"] for u in await get_served_users()]
            chats = [c["chat_id"] for c in await get_served_chats()]
        elif "-users" in cmd:
            users = [u["user_id"] for u in await get_served_users()]
            chats = []
        elif "-chats" in cmd:
            chats = [c["chat_id"] for c in await get_served_chats()]
            users = []
        else:
            return await message.reply_text(
                "❗ Usage:\n/broadcast -all/-users/-chats [-forward]\nExample: /broadcast -all Hello"
            )

        if not users and not chats:
            return await message.reply_text("⚠ No recipients found.")

        if message.reply_to_message:
            content = message.reply_to_message
        else:
            txt = message.text
            for kw in ["/broadcast", "-forward", "-all", "-users", "-chats"]:
                txt = txt.replace(kw, "")
            txt = txt.strip()
            if not txt:
                return await message.reply_text("📝 Reply to a message or write text after the command.")
            content = txt

        total = len(users) + len(chats)
        sent_u = sent_c = failed = 0

        status = await message.reply_text(
            f"📢 <b>Broadcast started</b>\nMode: <code>{mode}</code>\n"
            f"👤 Users: <code>{len(users)}</code>\n👥 Chats: <code>{len(chats)}</code>\n"
            f"Total: <code>{total}</code>\n⏳ Sending slowly to avoid flood..."
        )

        async def deliver(cid, is_user, retry=3):
            nonlocal sent_u, sent_c, failed
            async with SEMAPHORE:
                try:
                    if isinstance(content, str):
                        await app.send_message(cid, content)
                    elif mode == "forward":
                        await app.forward_messages(cid, message.chat.id, [content.id])
                    else:
                        await content.copy(cid)

                    if is_user:
                        sent_u += 1
                    else:
                        sent_c += 1

                    await asyncio.sleep(random.uniform(1.5, 3.0))

                except FloodWait as e:
                    wait_time = e.value + 5
                    logger.warning(f"FloodWait {e.value}s for {cid}, pausing {wait_time}s")
                    await asyncio.sleep(wait_time)
                    if retry > 0:
                        return await deliver(cid, is_user, retry - 1)
                    failed += 1
                except (Forbidden, PeerIdInvalid):
                    failed += 1
                except RPCError as e:
                    logger.warning(f"RPCError: {e}")
                    failed += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Unexpected error {e}")
                    failed += 1
                    await asyncio.sleep(1.5)

        targets = [(uid, True) for uid in users] + [(cid, False) for cid in chats]

        # Sequential loop (safe mode)
        for idx, (cid, is_user) in enumerate(targets, start=1):
            await deliver(cid, is_user)
            if idx % 100 == 0:
                await status.edit_text(
                    f"📢 <b>Broadcast Progress</b>\n"
                    f"Sent: {idx}/{total}\n"
                    f"Users: {sent_u} | Chats: {sent_c}\n"
                    f"Failed: {failed}\n⏳ Sending slowly..."
                )

        await status.edit_text(
            f"✅ <b>Broadcast Completed</b>\nMode: <code>{mode}</code>\n"
            f"👤 Users Sent: <code>{sent_u}</code>\n"
            f"👥 Chats Sent: <code>{sent_c}</code>\n"
            f"📦 Total: <code>{sent_u + sent_c}</code>\n"
            f"❌ Failed: <code>{failed}</code>"
        )

    except Exception as e:
        logger.exception(e)
        await message.reply_text(f"🚫 Broadcast failed: {e}")


# Adminlist cleaner loop (kept as is)
async def auto_clean():
    while True:
        await asyncio.sleep(10)
        try:
            chats = await get_active_chats()
            for chat_id in chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                async for member in app.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
                    if getattr(member, "privileges", None) and member.privileges.can_manage_video_chats:
                        adminlist[chat_id].append(member.user.id)
                for username in await get_authuser_names(chat_id):
                    adminlist[chat_id].append(await alpha_to_int(username))
        except Exception as e:
            logger.warning(f"AutoClean error: {e}")
