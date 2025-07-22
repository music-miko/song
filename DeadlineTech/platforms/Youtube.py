import asyncio
import os
import re
import json
import glob
import random
import logging
import aiofiles
import httpx
import aiohttp
import time
import aiofiles
import aiofiles.os as aioos
import config
import requests
import yt_dlp
from typing import Union
from aiocache import cached, Cache
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from DeadlineTech.utils.database import is_on_off
from youtubesearchpython.__future__ import VideosSearch
from DeadlineTech.utils.formatters import time_to_seconds



API_VIDEO_MODE = False


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


def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]

    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file


@cached(ttl=60000, cache=Cache.MEMORY)  # Cache for 1000 minutes (60000 seconds)
async def check_local_file(video_id: str):
    download_folder = "downloads"
    for ext in ["mp3", "m4a", "webm", "opus"]:
        file_path = os.path.join(download_folder, f"{video_id}.{ext}")
        if os.path.exists(file_path):  # lightweight sync check, usually okay
            return file_path
    return None




# ✅ Function to check if stream URL is valid
async def is_valid_stream_url(url: str) -> bool:
    try:
        timeout = httpx.Timeout(5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.head(url)
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "").lower()
                return any(x in content_type for x in ["audio", "video", "webm", "m4a", "mp4"])
    except Exception as e:
        print(f"⚠️ Validation error: {e}")
    return False



# 🔄 Function to get and validate stream URL with retry
async def fetch_stream_url(link: str) -> str | None:
    global ReqGetStream, SuccessGetStream, FailedGetStream, TimeOutStream

    ReqGetStream += 1

    try:
        video_id = link.split("v=")[-1].split("&")[0]
    except Exception as e:
        print(f"❌ Could not extract video ID: {e}")
        FailedGetStream += 1
        return None

    api_key = getattr(config, "API_KEY", None)
    if not api_key:
        print("❌ API_KEY not found in config.")
        FailedGetStream += 1
        return None
        
    api_url = getattr(config, "API_URL", None)
    if not api_url:  # ← FIXED HERE
        print("❌ API_URL not found in config.")
        FailedGetStream += 1
        return None

    url = f"{api_url}/get/stream/{video_id}?key={api_key}"
    timeout = httpx.Timeout(15.0)
    print(f"🔗 Requesting: {url}")

    start_time = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout) as client:
        attempt = 1
        while attempt <= 5 and (time.perf_counter() - start_time) < 15.0:
            elapsed = time.perf_counter() - start_time

            try:
                print(f"🔁 Attempt #{attempt} (Elapsed: {round(elapsed, 2)}s)")
                response = await client.get(url)
                connect_time = round(response.elapsed.total_seconds(), 3)
                total_time = round(time.perf_counter() - start_time, 3)

                print(f"⚡ Connected in: {connect_time}s")
                print(f"📦 Response received in: {total_time}s")

                if response.status_code == 200:
                    data = response.json()
                    stream_url = data.get("stream_url")

                    if stream_url:
                        print(f"🎵 Received stream URL: {stream_url}")
                        valid = await is_valid_stream_url(stream_url)
                        if valid:
                            print("✅ Stream URL is valid.")
                            SuccessGetStream += 1
                            return stream_url
                        else:
                            print("❌ Invalid stream content. Retrying...")
                    else:
                        print("⚠️ stream_url missing in response. Retrying...")

                else:
                    print(f"❌ API error: {response.status_code}")
            except httpx.ConnectTimeout:
                print("⏱️ Connection timed out.")
            except httpx.ReadTimeout:
                print("⏱️ Read timed out.")
            except Exception as e:
                print(f"⚠️ Request error: {e}")

            await asyncio.sleep(0.5)
            attempt += 1

    print("⏱️ Total timeout exceeded (15s) or max attempts (5) reached.")
    TimeOutStream += 1
    FailedGetStream += 1
    return None


# 🔄 Fetch video stream URL from /get/videostream/
async def fetch_video_stream_url(link: str) -> str | None:
    global ReqGetVideoStream, SuccessGetVideoStream, FailedGetVideoStream, TimeOutVideoStream

    ReqGetVideoStream += 1

    try:
        video_id = link.split("v=")[-1].split("&")[0]
    except Exception as e:
        print(f"❌ Could not extract video ID: {e}")
        FailedGetVideoStream += 1
        return None

    api_key = getattr(config, "API_KEY", None)
    if not api_key:
        print("❌ API_KEY not found in config.")
        FailedGetVideoStream += 1
        return None

    api_url = getattr(config, "API_URL", None)
    if not api_url:
        print("❌ API_URL not found in config.")
        FailedGetVideoStream += 1  # ← fixed (was incrementing FailedGetStream by mistake)
        return None

    url = f"{api_url}/get/videostream/{video_id}?key={api_key}"
    timeout = httpx.Timeout(20.0)
    print(f"🔗 Requesting: {url}")

    start_time = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout) as client:
        attempt = 1
        while attempt <= 5 and (time.perf_counter() - start_time) < 20.0:
            elapsed = time.perf_counter() - start_time

            try:
                print(f"🔁 Attempt #{attempt} (Elapsed: {round(elapsed, 2)}s)")
                response = await client.get(url)
                connect_time = round(response.elapsed.total_seconds(), 3)
                total_time = round(time.perf_counter() - start_time, 3)

                print(f"⚡ Connected in: {connect_time}s")
                print(f"📦 Response received in: {total_time}s")

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "done":
                        stream_url = data.get("stream_url")
                        if stream_url:
                            print(f"🎥 Received video stream URL: {stream_url}")
                            valid = await is_valid_stream_url(stream_url)
                            if valid:
                                print("✅ Stream URL is valid.")
                                SuccessGetVideoStream += 1
                                return stream_url
                            else:
                                print("❌ Invalid video stream content. Retrying...")
                        else:
                            print("⚠️ 'stream_url' missing in response. Retrying...")
                    else:
                        print(f"⚠️ Unexpected status: {data.get('status')}. Retrying...")

                elif response.status_code == 404:
                    data = response.json()
                    print(f"❌ Stream fetch failed: {data.get('error')}")
                    FailedGetVideoStream += 1
                    return None

                else:
                    print(f"❌ Unexpected status code: {response.status_code}. Retrying...")

            except httpx.ConnectTimeout:
                print("⏱️ Connection timed out.")
            except httpx.ReadTimeout:
                print("⏱️ Read timed out.")
            except Exception as e:
                print(f"⚠️ Request error: {e}")

            await asyncio.sleep(0.5)
            attempt += 1

    print("⏱️ Total timeout exceeded (20s) or max attempts (5) reached.")
    TimeOutVideoStream += 1
    FailedGetVideoStream += 1
    return None


# 📊 Function to get both audio & video stream stats
def get_stream_stats() -> str:
    return (
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
    )







async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
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
    
    # Helper method to extract YouTube video ID from URL
    def extract_video_id(self, url: str) -> Union[str, None]:
        patterns = [
            re.compile(r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})'),
            re.compile(r'youtu\.be\/([0-9A-Za-z_-]{11})'),
            re.compile(r'youtube\.com\/(?:.*\/)?([0-9A-Za-z_-]{11})')
        ]
        for pattern in patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

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
        result_url = text[offset : offset + length]

        # --- START: Standardize YouTube video URL if detected ---
        video_id = self.extract_video_id(result_url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        # --- END: Standardize YouTube video URL if detected ---
        return result_url

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
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",cookie_txt_file(),
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
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
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
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_txt_file()}
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
            config.ReqYt += 1
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            try:
                info = x.extract_info(link, False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if not os.path.exists(xyz):
                    x.download([link])
                if os.path.exists(xyz):
                    config.DlYt += 1
                    return xyz
            except Exception as e:
                print(e)
                config.FailedYt += 1
                return None

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
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
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
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

        try:
            if songvideo:
                config.songvideo_requests += 1
                try:
                    print("📥 Downloading songvideo via song_video_dl()")
                    await loop.run_in_executor(None, song_video_dl)
                    fpath = f"downloads/{title}.mp4"
                    config.songvideo_success += 1
                except Exception as e:
                    print(f"⚠️ song_video_dl failed: {e}")
                    await loop.run_in_executor(None, song_video_dl)
                    fpath = f"downloads/{title}.mp4"
                    config.songvideo_failed += 1
                return fpath, True

            elif songaudio:
                config.songaudio_requests += 1
                try:
                    print("🎧 Downloading songaudio via song_audio_dl()")
                    await loop.run_in_executor(None, song_audio_dl)
                    fpath = f"downloads/{title}.mp3"
                    config.songaudio_success += 1
                except Exception as e:
                    print(f"⚠️ song_audio_dl failed: {e}")
                    await loop.run_in_executor(None, song_audio_dl)
                    fpath = f"downloads/{title}.mp3"
                    config.songaudio_failed += 1
                return fpath, True

            elif video:
                config.video_requests += 1
                try:
                    if API_VIDEO_MODE:
                        print("🎬 Trying to fetch video stream URL via API...")
                        stream_url = await fetch_video_stream_url(link)
                        if stream_url:
                            config.video_success += 1
                            return stream_url, True
                        else:
                            raise Exception("API video stream URL fetch failed.")
                    else:
                        raise Exception("API_VIDEO_MODE is disabled.")

                except Exception as e:
                    print(f"⚠️ API failed: {e}")
                    print("🔁 Falling back to yt-dlp...")

                    try:
                        proc = await asyncio.create_subprocess_exec(
                            "yt-dlp",
                            "--cookies", cookie_txt_file(),
                            "-g",
                            "-f", "best[height<=?720][width<=?1280]",
                            f"{link}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        if stdout:
                            downloaded_file = stdout.decode().split("\n")[0]
                            direct = False
                            if downloaded_file:
                                config.video_success += 1
                            return downloaded_file, direct
                        else:
                            raise Exception("yt-dlp direct URL fetch failed")

                    except Exception as e:
                        print(f"⚠️ yt-dlp direct fetch failed: {e}")
                        print("📏 Checking file size...")

                        file_size = await check_file_size(link)
                        if not file_size:
                            print("❌ Could not determine file size.")
                            config.video_failed += 1
                            return None, True

                        total_size_mb = file_size / (1024 * 1024)
                        if total_size_mb > 250:
                            print(f"🚫 File size {total_size_mb:.2f} MB exceeds 250 MB limit.")
                            config.video_failed += 1
                            return None, True

                        print("📥 Downloading using video_dl() as last resort...")
                        downloaded_file = await loop.run_in_executor(None, video_dl)
                        config.video_success += 1
                        return downloaded_file, True

            else:
                config.audio_requests += 1
                print("🎵 Trying to fetch audio stream URL via API...")
                try:
                    stream_url = await fetch_stream_url(link)
                    if stream_url:
                        config.audio_success += 1
                        return stream_url, True
                    else:
                        raise Exception("API audio stream URL fetch failed.")
                except Exception as e:
                    print(f"⚠️ API failed: {e}")
                    print("🔁 Falling back to audio_dl()...")

                    try:
                        path = await loop.run_in_executor(None, audio_dl)
                        if path:
                            config.audio_success += 1
                        return path, True
                    except Exception as e:
                        print(f"❌ audio_dl failed: {e}")
                        config.audio_failed += 1
                        return None, True

        except Exception as e:
            print(f"❌ Unhandled error during download: {e}")
            return None, True

