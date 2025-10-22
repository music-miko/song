import asyncio
import random
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait, RPCError, Forbidden, PeerIdInvalid

from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from AnonXMusic.utils.decorators.language import language
from AnonXMusic.utils.formatters import alpha_to_int
from config import adminlist

IS_BROADCASTING = False


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def broadcast_message(client, message, _):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return await message.reply_text("⚠️ Broadcast already running, please wait until it finishes.")

    # Get message / query
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
        query = None
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1]
        for flag in ["-pin", "-nobot", "-pinloud", "-assistant", "-user"]:
            query = query.replace(flag, "")
        query = query.strip()
        if not query:
            return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    # ----------------------------------- CHATS -----------------------------------
    if "-nobot" not in message.text:
        sent, pin, failed = 0, 0, 0
        schats = await get_served_chats()
        chats = [int(chat["chat_id"]) for chat in schats]

        for chat_id in chats:
            try:
                if message.reply_to_message:
                    msg = await app.forward_messages(chat_id, y, x)
                else:
                    msg = await app.send_message(chat_id, text=query)

                # Handle pin flags
                if "-pin" in message.text:
                    try:
                        await msg.pin(disable_notification=True)
                        pin += 1
                    except:
                        pass
                elif "-pinloud" in message.text:
                    try:
                        await msg.pin(disable_notification=False)
                        pin += 1
                    except:
                        pass

                sent += 1
                await asyncio.sleep(random.uniform(1.5, 3.0))

            except FloodWait as fw:
                wait = int(fw.value)
                if wait > 300:
                    failed += 1
                    continue
                await asyncio.sleep(wait + 5)
            except (Forbidden, PeerIdInvalid):
                failed += 1
                continue
            except RPCError:
                failed += 1
                await asyncio.sleep(2)
            except Exception:
                failed += 1
                await asyncio.sleep(1.5)

        try:
            await message.reply_text(_["broad_3"].format(sent, pin))
        except:
            pass

    # ----------------------------------- USERS -----------------------------------
    if "-user" in message.text:
        susr, failed = 0, 0
        susers = await get_served_users()
        users = [int(user["user_id"]) for user in susers]

        for user_id in users:
            try:
                if message.reply_to_message:
                    await app.forward_messages(user_id, y, x)
                else:
                    await app.send_message(user_id, text=query)
                susr += 1
                await asyncio.sleep(random.uniform(1.5, 3.0))
            except FloodWait as fw:
                wait = int(fw.value)
                if wait > 300:
                    failed += 1
                    continue
                await asyncio.sleep(wait + 5)
            except (Forbidden, PeerIdInvalid):
                failed += 1
                continue
            except RPCError:
                failed += 1
                await asyncio.sleep(2)
            except Exception:
                failed += 1
                await asyncio.sleep(1.5)

        try:
            await message.reply_text(_["broad_4"].format(susr))
        except:
            pass

    # ----------------------------------- ASSISTANTS -----------------------------------
    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from AnonXMusic.core.userbot import assistants

        for num in assistants:
            sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    if message.reply_to_message:
                        await client.copy_messages(dialog.chat.id, y, x)
                    else:
                        await client.send_message(dialog.chat.id, text=query)
                    sent += 1
                    await asyncio.sleep(2.5)
                except FloodWait as fw:
                    wait = int(fw.value)
                    if wait > 300:
                        continue
                    await asyncio.sleep(wait)
                except:
                    continue
            text += _["broad_7"].format(num, sent)

        try:
            await aw.edit_text(text)
        except:
            pass

    IS_BROADCASTING = False


# ----------------------------------- AUTO CLEAN -----------------------------------
async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
                        if user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue


asyncio.create_task(auto_clean())
