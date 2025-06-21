# Powered By Team DeadlineTech ✨

import os
import sys
import time
import asyncio
import importlib
import subprocess
import logging

from pyrogram import idle
from pyrogram.types import BotCommand
from pytgcalls.exceptions import NoActiveGroupCall

import config
from DeadlineTech import LOGGER, app, userbot
from DeadlineTech.core.call import Anony
from DeadlineTech.misc import sudo
from DeadlineTech.plugins import ALL_MODULES
from DeadlineTech.utils.database import get_banned_users, get_gbanned
from DeadlineTech.utils.crash_reporter import setup_global_exception_handler
from config import BANNED_USERS

OWNER_ID = 7321657753  # Alert target if everything fails

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
LOG = logging.getLogger("DeadlineTechMain")

async def start_bot():
    setup_global_exception_handler()

    if not any([config.STRING1, config.STRING2, config.STRING3, config.STRING4, config.STRING5]):
        LOG.error("Assistant client variables not set! Exiting.")
        return

    await sudo()

    try:
        for uid in await get_gbanned():
            BANNED_USERS.add(uid)
        for uid in await get_banned_users():
            BANNED_USERS.add(uid)
    except Exception as e:
        LOG.warning(f"Failed to fetch banned users: {e}")

    await app.start()

    await app.set_bot_commands([
        BotCommand("start", "Sᴛᴀʀᴛ's Tʜᴇ Bᴏᴛ"),
        BotCommand("ping", "Cʜᴇᴄᴋ ɪғ ʙᴏᴛ ɪs ᴀʟɪᴠᴇ"),
        BotCommand("help", "Gᴇᴛ Cᴏᴍᴍᴀɴᴅs Lɪsᴛ"),
        BotCommand("music", "download the songs 🎵"), 
        BotCommand("play", "Pʟᴀʏ Mᴜsɪᴄ ɪɴ Vᴄ"),
        BotCommand("vplay", "starts Streaming the requested Video Song"), 
        BotCommand("playforce", "forces to play your requested song"), 
        BotCommand("vplayforce", "forces to play your requested Video song"), 
        BotCommand("pause", "pause the current playing stream"), 
        BotCommand("resume", "resume the paused stream"), 
        BotCommand("skip", "skip the current playing stream"), 
        BotCommand("end", "end the current stream"), 
        BotCommand("player", "get a interactive player panel"), 
        BotCommand("queue", "shows the queued tracks list"), 
        BotCommand("auth", "add a user to auth list"), 
        BotCommand("unauth", "remove a user from the auth list"), 
        BotCommand("authusers", "shows the list of the auth users"), 
        BotCommand("cplay", "starts streaming the requested audio on channel"), 
        BotCommand("cvplay", "Starts Streaming the video track on channel"), 
        BotCommand("channelplay", "connect channel to a group and start streaming"), 
        BotCommand("shuffle", "shuffle's the queue"), 
        BotCommand("seek", "seek the stream to the given duration"), 
        BotCommand("seekback", "backward seek the stream"), 
        BotCommand("speed", "for adjusting the audio playback speed"), 
        BotCommand("loop", "enables the loop for the given value"), 
        BotCommand("stats", "check statistics of the Bot")
    ])

    for mod in ALL_MODULES:
        importlib.import_module(f"DeadlineTech.plugins" + mod)
    LOG.info("✅ All plugins loaded.")

    await userbot.start()
    await Anony.start()

    try:
        await Anony.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOG.error("Start a video chat in your log group!")
        return
    except Exception:
        pass

    await Anony.decorators()
    LOG.info("✅ DeadlineTech Music Bot started.")
    await idle()

    await app.stop()
    await userbot.stop()
    await Anony.stop()
    LOG.info("🛑 Bot stopped gracefully.")

async def notify_shutdown():
    try:
        await app.start()
        await app.send_message(
            OWNER_ID,
            "❌ <b>Bot crashed and retry failed.</b>\nShutting down permanently for safety."
        )
        await app.stop()
    except Exception as e:
        LOG.warning(f"Could not notify owner: {e}")

async def runner():
    try:
        await start_bot()
    except Exception as e:
        LOG.exception("❌ Bot crashed unexpectedly.")
        LOG.info("🔁 Attempting restart via 'bash start'...")

        # Restart via bash script
        try:
            subprocess.Popen(["bash", "start"])
            sys.exit(0)  # exit current (crashed) instance
        except Exception as restart_error:
            LOG.error(f"⚠️ Failed to restart via bash: {restart_error}")
            await notify_shutdown()
            sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOG.info("👋 Bot stopped manually.")
