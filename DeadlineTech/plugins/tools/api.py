from pyrogram import Client, filters
from pyrogram.types import Message
import config
from DeadlineTech import app
from DeadlineTech.misc import SUDOERS


def get_download_stats_message() -> str:
    """Generate a formatted message showing download statistics."""
    
    # API stats
    total_api = config.RequestApi
    success_api = config.downloadedApi
    failed_api = config.failedApi
    link_failed = config.failedApiLinkExtract
    success_rate_api = (success_api / total_api * 100) if total_api else 0

    # YouTube stats
    total_yt = config.ReqYt
    success_yt = config.DlYt
    failed_yt = config.FailedYt
    success_rate_yt = (success_yt / total_yt * 100) if total_yt else 0

    # Overall stats
    total_all = total_api + total_yt
    success_all = success_api + success_yt
    success_rate_all = (success_all / total_all * 100) if total_all else 0

    return (
        "📊 <b>Download Stats Summary</b>\n\n"
        "🧩 <b>API Stats</b>\n"
        f"🔄 Total API Requests: <code>{total_api}</code>\n"
        f"✅ Successful API Downloads: <code>{success_api}</code>\n"
        f"❌ Failed API Downloads: <code>{failed_api}</code>\n"
        f"⚠️ Link Extraction Failures: <code>{link_failed}</code>\n"
        f"📈 API Success Rate: <code>{success_rate_api:.2f}%</code>\n\n"
        "🎥 <b>YouTube Stats</b>\n"
        f"🔄 Total YouTube Requests: <code>{total_yt}</code>\n"
        f"✅ Successful YouTube Downloads: <code>{success_yt}</code>\n"
        f"❌ Failed YouTube Downloads: <code>{failed_yt}</code>\n"
        f"📈 YouTube Success Rate: <code>{success_rate_yt:.2f}%</code>\n\n"
        "📊 <b>Overall</b>\n"
        f"🧮 Combined Total Requests: <code>{total_all}</code>\n"
        f"🏁 Total Successful Downloads: <code>{success_all}</code>\n"
        f"📉 Total Success Rate: <code>{success_rate_all:.2f}%</code>\n\n"
        "📥 Keep going strong!"
    )


@app.on_message(filters.command("dstats") & SUDOERS)
async def download_stats_handler(client: Client, message: Message):
    """Send the download statistics when /dstats is used by a sudo user."""
    stats_msg = get_download_stats_message()
    await message.reply(stats_msg)
