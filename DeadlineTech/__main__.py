# ==========================================================
# 🔒 All Rights Reserved © Team DeadlineTech
# 📁 This file is part of the DeadlineTech Project.
# ==========================================================

import asyncio
import importlib
import time
from pyrogram.types import BotCommand
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from DeadlineTech import LOGGER, app, userbot
from DeadlineTech.core.call import Anony
from DeadlineTech.misc import sudo
from DeadlineTech.plugins import ALL_MODULES
from DeadlineTech.utils.database import get_banned_users, get_gbanned
from DeadlineTech.utils.crash_reporter import setup_global_exception_handler
from config import BANNED_USERS

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

async def start_bot():
    # ✅ Enable global crash handler
    setup_global_exception_handler()

    if not any([config.STRING1, config.STRING2, config.STRING3, config.STRING4, config.STRING5]):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        return

    await sudo()

    try:
        gbanned = await get_gbanned()
        banned = await get_banned_users()
        for user_id in gbanned + banned:
            BANNED_USERS.add(user_id)
    except Exception as e:
        LOGGER("Init").warning(f"Couldn't load banned users: {e}")

    await app.start()

    await app.set_bot_commands([
        BotCommand("start", "Sᴛᴀʀᴛ's Tʜᴇ Bᴏᴛ"),
        BotCommand("ping", "Cʜᴇᴄᴋ ɪғ ʙᴏᴛ ɪs ᴀʟɪᴠᴇ"),
        BotCommand("help", "Gᴇᴛ Cᴏᴍᴍᴀɴᴅs Lɪsᴛ"),
        BotCommand("music", "Download the songs 🎵"),
        BotCommand("play", "Pʟᴀʏ Mᴜsɪᴄ ɪɴ Vᴄ"),
        BotCommand("vplay", "Start streaming the requested Video Song"),
        BotCommand("playforce", "Force play your requested song"),
        BotCommand("vplayforce", "Force play your requested Video song"),
        BotCommand("pause", "Pause the current playing stream"),
        BotCommand("resume", "Resume the paused stream"),
        BotCommand("skip", "Skip the current playing stream"),
        BotCommand("end", "End the current stream"),
        BotCommand("player", "Get an interactive player panel"),
        BotCommand("queue", "Show the queued tracks list"),
        BotCommand("auth", "Add a user to auth list"),
        BotCommand("unauth", "Remove a user from the auth list"),
        BotCommand("authusers", "Show list of auth users"),
        BotCommand("cplay", "Stream audio in a channel"),
        BotCommand("cvplay", "Stream video in a channel"),
        BotCommand("channelplay", "Link channel to group and stream"),
        BotCommand("shuffle", "Shuffle the queue"),
        BotCommand("seek", "Seek the stream to a specific duration"),
        BotCommand("seekback", "Seek backward in stream"),
        BotCommand("speed", "Adjust audio playback speed"),
        BotCommand("loop", "Enable loop playback"),
        BotCommand("stats", "Bot statistics"),
    ])

    for module in ALL_MODULES:
        importlib.import_module("DeadlineTech.plugins." + module)
    LOGGER("DeadlineTech.plugins").info("✅ All modules imported. Starting...")

    await userbot.start()
    await Anony.start()

    try:
        await Anony.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("DeadlineTech").error(
            "Video chat is off in log group/channel.\nStopping bot..."
        )
        return
    except Exception as e:
        LOGGER("DeadlineTech").warning(f"Stream setup skipped: {e}")

    await Anony.decorators()
    LOGGER("DeadlineTech").info("✅ DeadlineTech Music Bot started and running.")
    await idle()

    await app.stop()
    await userbot.stop()
    LOGGER("DeadlineTech").info("🛑 DeadlineTech Bot stopped.")


if __name__ == "__main__":
    retries = 0
    while retries <= MAX_RETRIES:
        try:
            asyncio.get_event_loop().run_until_complete(start_bot())
            break
        except Exception as err:
            retries += 1
            LOGGER("Main").error(f"Error occurred: {err}. Retrying in {RETRY_DELAY}s... ({retries}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    else:
        LOGGER("Main").critical("❌ Failed to start bot after multiple retries.")
