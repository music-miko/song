import asyncio
import os
import re
import json
import glob
import random
import logging
import aiohttp
import config
import time
import requests
import yt_dlp
from pathlib import Path
from typing import Union
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from youtubesearchpython.__future__ import VideosSearch
from ..utils.database import is_on_off
from ..utils.formatters import time_to_seconds

API_VIDEO_MODE = True


MIN_FILE_SIZE_BYTES = 10 * 1024
RETRIES = 3
MAX_TOTAL_TIME = 12
# ----- logger setup (minimal) -----
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
# ---------------------------------------------------------------
# Stream Url Counters
ReqGetStream = 0
SuccessGetStream = 0
FailedGetStream = 0
TimeOutStream = 0
# Stream Video Url Counters
ReqGetVideoStream = 0
SuccessGetVideoStream = 0
FailedGetVideoStream = 0
TimeOutVideoStream = 0
# 📊 Function to get both audio & video stream stats
def get_stream_stats() -> str:
    return (
        "<pre><code>"
        "📊 Stream Fetch Stats:\n\n"
        "🎵 Audio Stream:\n"
        f"• 🔁 Total Requests: {ReqGetStream}\n"
        f"• ✅ Success: {SuccessGetStream}\n"
        f"• ❌ Failed: {FailedGetStream}\n"
        f"• ⏱️ Timed Out: {TimeOutStream}\n\n"
        "🎥 Video Stream:\n"
        f"• 🔁 Total Requests: {ReqGetVideoStream}\n"
        f"• ✅ Success: {SuccessGetVideoStream}\n"
        f"• ❌ Failed: {FailedGetVideoStream}\n"
        f"• ⏱️ Timed Out: {TimeOutVideoStream}"
        "</code></pre>"
    )


async def fetch_stream_url(link: str, video: bool = False) -> str | None:
    try:
        video_id = link.split("v=")[-1].split("&")[0]
        if not video_id:
            raise ValueError("Empty video ID extracted")
    except Exception as e:
        raise ValueError(f"❌ Could not extract video ID from link: {link}") from e

    api_key = getattr(config, "API_KEY", None)
    api_url = getattr(config, "API_URL", None)
    if not api_key or not api_url:
        raise RuntimeError("❌ API_KEY or API_URL missing in config.")

    url = f"{api_url}/song/{video_id}?key={api_key}"
    if video:
        url += "&video=True"

    timeout = aiohttp.ClientTimeout(total=10)
    print(f"🔗 Requesting ({'Video' if video else 'Audio'}): {url}")

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, 3):  # ✅ Max 2 attempts
            try:
                print(f"🔁 {'Video' if video else 'Audio'} Attempt #{attempt}")
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "done":
                            stream_url = data.get("stream_url")
                            if stream_url:
                                print(f"🎬 Direct stream URL ready: {stream_url}")
                                return stream_url
                    elif response.status == 404:
                        return None
            except Exception as e:
                print(f"⚠️ Request error ({'Video' if video else 'Audio'}): {e}")

            if attempt < 2:  # wait before retry only if another attempt left
                await asyncio.sleep(0.5)

    return None


async def download_file(link: str, video: bool = False) -> str | None:
    try:
        video_id = link.split("v=")[-1].split("&")[0]
        if not video_id:
            raise ValueError("Empty video ID extracted")
    except Exception as e:
        raise ValueError(f"❌ Could not extract video ID from link: {link}") from e

    folder = Path("downloads/video" if video else "downloads/audio")
    folder.mkdir(parents=True, exist_ok=True)

    ext = ".mp4" if video else ".m4a"
    filepath = folder / f"{video_id}{ext}"
    temp_path = filepath.with_suffix(filepath.suffix + ".part")

    if filepath.exists():
        print(f"ℹ️ File already downloaded: {filepath}")
        return str(filepath)

    if temp_path.exists():
        print(f"⏳ Another download in progress for {video_id}, waiting...")
        for _ in range(30):
            if filepath.exists():
                print(f"✅ Download finished by another process: {filepath}")
                return str(filepath)
            await asyncio.sleep(0.75)
        print("❌ Timed out waiting for ongoing download.")
        return None

    for attempt in range(1, 4):
        try:
            stream_url = await fetch_stream_url(link, video=video)
            if not stream_url:
                print("❌ Failed to get stream URL.")
                return None

            timeout = aiohttp.ClientTimeout(total=None)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(stream_url) as response:
                    if response.status != 200:
                        print(f"❌ Failed to download: HTTP {response.status}")
                        raise Exception(f"HTTP {response.status}")

                    with open(temp_path, "wb") as f:
                        while True:
                            chunk = await response.content.read(1024 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)

            temp_path.rename(filepath)
            print(f"✅ Download completed: {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"⚠️ Download attempt {attempt} failed: {e}")
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

            if attempt < 3:
                await asyncio.sleep(1)
            else:
                print("❌ All download attempts failed.")
                return None


def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir):
        return None
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        return None
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file


async def check_file_size(link):
    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        if not cookie_file:
            print("No cookies found. Cannot check file size.")
            return None
            
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Try video API first
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
        except Exception as e:
            print(f"Video API failed: {e}")
        
        # Fallback to cookies
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return 0, "No cookies found. Cannot download video."
            
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return []
            
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return [], link
            
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_file}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()
        def audio_dl():
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found. Cannot download audio.")
                
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile" : cookie_file,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found. Cannot download video.")
                
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile" : cookie_file,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found. Cannot download song video.")
                
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile" : cookie_file,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            cookie_file = cookie_txt_file()
            if not cookie_file:
                raise Exception("No cookies found. Cannot download song audio.")
                
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile" : cookie_file,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            fpath = await download_file(link)
            return fpath
        elif songaudio:
            fpath= await download_file(link)
            return fpath
        elif video:
            # Try video API first
            try:
                downloaded_file = await download_file(link, video=True)
                if downloaded_file:
                    direct = True
                    return downloaded_file, direct
            except Exception as e:
                print(f"Video API failed: {e}")
            
            # Fallback to cookies
            cookie_file = cookie_txt_file()
            if not cookie_file:
                print("No cookies found. Cannot download video.")
                return None, None
                
            if await is_on_off(1):
                direct = True
                downloaded_file = await download_file(link)
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", cookie_file,
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = False
                else:
                   file_size = await check_file_size(link)
                   if not file_size:
                     print("None file Size")
                     return None, None
                   total_size_mb = file_size / (1024 * 1024)
                   if total_size_mb > 250:
                     print(f"File size {total_size_mb:.2f} MB exceeds the 100MB limit.")
                     return None, None
                   direct = True
                   downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            direct = True
            try:
                downloaded_file = await download_file(link)
                if downloaded_file:
                    return downloaded_file, direct
            except Exception as e:
                print(e)
            # Fallback to cookies
            cookie_file = cookie_txt_file()
            if not cookie_file:
                print("No cookies found. Cannot download video.")
                return None, None
            
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            
        return downloaded_file, direct



