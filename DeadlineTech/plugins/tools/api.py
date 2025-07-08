from pyrogram import Client, filters
from pyrogram.types import Message
import config
from DeadlineTech import app
from DeadlineTech.misc import SUDOERS

# Function to generate stats message
def get_download_stats_message():
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

    # Combined stats
    total_all = total_api + total_yt
    success_all = success_api + success_yt
    success_rate_all = (success_all / total_all * 100) if total_all else 0

    return f"""📊 <b>Download Stats Summary</b>

🧩 <b>API Stats</b>
🔄 Total API Requests: <code>{total_api}</code>
✅ Successful API Downloads: <code>{success_api}</code>
❌ Failed API Downloads: <code>{failed_api}</code>
⚠️ Link Extraction Failures: <code>{link_failed}</code>
📈 API Success Rate: <code>{success_rate_api:.2f}%</code>

🎥 <b>YouTube Stats</b>
🔄 Total YouTube Requests: <code>{total_yt}</code>
✅ Successful YouTube Downloads: <code>{success_yt}</code>
❌ Failed YouTube Downloads: <code>{failed_yt}</code>
📈 YouTube Success Rate: <code>{success_rate_yt:.2f}%</code>

📊 <b>Overall</b>
🧮 Combined Total Requests: <code>{total_all}</code>
🏁 Total Successful Downloads: <code>{success_all}</code>
📉 Total Success Rate: <code>{success_rate_all:.2f}%</code>

📥 Keep going strong!
"""

# Command handler
@app.on_message(filters.command("dstats") & SUDOERS)
async def download_stats_handler(client, message: Message):
    stats_msg = get_download_stats_message()
    await message.reply(stats_msg, parse_mode="html")
