import asyncio
import os
import re
import json
import glob
import random
import logging
import aiohttp
import aiofiles
import config
import requests
import yt_dlp
from typing import Union
from aiocache import cached, Cache
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from AviaxMusic.utils.database import is_on_off
from youtubesearchpython.__future__ import VideosSearch
from AviaxMusic.utils.formatters import time_to_seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MIN_FILE_SIZE_BYTES = 10 * 1024  # 0.01 MB = 10 KB

from config import API_URL, API_KEY    

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

async def download_file_with_cleanup(session, download_url, final_path):
    temp_path = final_path + ".part"
    try:
        async with session.get(download_url) as file_response:
            if file_response.status != 200:
                print(f"Failed to start download, status: {file_response.status}")
                return None

            async with aiofiles.open(temp_path, 'wb') as f:
                while True:
                    chunk = await file_response.content.read(8192)
                    if not chunk:
                        break
                    await f.write(chunk)

        size = os.path.getsize(temp_path)
        if size < MIN_FILE_SIZE_BYTES:
            print(f"File too small ({size} bytes), deleting partial file")
            await aiofiles.os.remove(temp_path)
            return None

        os.rename(temp_path, final_path)
        return final_path

    except Exception as e:
        print(f"Error during download or save: {e}")
        # Cleanup partial file if exists
        if await aiofiles.os.path.exists(temp_path):
            await aiofiles.os.remove(temp_path)
        return None

async def download_song(link: str):
    config.RequestApi += 1
    video_id = link.split('v=')[-1].split('&')[0]

    # Check if file already exists
    file_path = await check_local_file(video_id)
    if file_path:
        config.downloadedApi += 1
        logger.info(f"[CacheHit] File already exists: {file_path}")
        return file_path

    song_url = f"{API_URL}/song/{video_id}?key={API_KEY}"
    async with aiohttp.ClientSession() as session:
        for attempt in range(6):
            try:
                async with session.get(song_url) as response:
                    try:
                        data = await response.json()
                    except Exception:
                        text = await response.text()
                        logger.error(f"⚠️ Failed to parse JSON: {text}")
                        return None

                    if response.status == 429:
                        logger.warning(f"❌ API rate limit hit: {data.get('error', 'Too Many Requests')}")
                        return None

                    if response.status == 401:
                        logger.error(f"❌ API auth failed — check API key. Error: {data.get('error', 'Unauthorized')}")
                        return None

                    if response.status != 200:
                        raise Exception(f"API failed with status code {response.status}")

                    status = data.get("status", "").lower()

                    if status == "done":
                        download_url = data.get("download_url")
                        if not download_url:
                            raise Exception("API did not provide download_url")
                        break

                    elif status == "downloading":
                        await asyncio.sleep(5)  # don't reduce otherwise rate limit will block your ip
                        logger.warning(f"[OnApi] Still downloading: {video_id}")
                    else:
                        err_msg = data.get("error") or data.get("message") or f"Unexpected status: {status}"
                        raise Exception(f"API error: {err_msg}")

            except Exception as e:
                logger.error(f"[FAIL] {e}")
                return None
        else:
            config.failedApiLinkExtract += 1
            logger.error("⏱️ Max retries reached while polling API.")
            return None

        file_format = data.get("format", "mp3")
        file_path = os.path.join("downloads", f"{video_id}.{file_format}")

        file_path_result = await download_file_with_cleanup(session, download_url, file_path)
        if file_path_result is None:
            config.failedApi += 1
            logger.error(f"[DL Failed] Could not save file for: {video_id}")
            return None

        config.downloadedApi += 1
        logger.info(f"[Downloaded] ✅ {file_path}")
        return file_path_result



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
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile" : cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            config.ReqYt += 1
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
                "cookiefile" : cookie_txt_file(),
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
                "cookiefile" : cookie_txt_file(),
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
                "cookiefile" : cookie_txt_file(),
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
                try:
                    fpath = await download_song(link)
                    if fpath is None:
                        print("download_song song_video download returned None, falling back")
                        await self.loop.run_in_executor(None, song_video_dl)
                        fpath = f"downloads/{title}.mp4"
                except Exception as e:
                    print("download_song song_video download returned None, falling back")
                    await self.loop.run_in_executor(None, song_video_dl)
                    fpath = f"downloads/{title}.mp4"
                return fpath, direct

            elif songaudio:
                try:
                    fpath = await download_song(link)
                    if fpath is None:
                        print("download_song song_audio download returned None, falling back")
                        await self.loop.run_in_executor(None, song_audio_dl)
                        fpath = f"downloads/{title}.mp3"
                except Exception as e:
                    print("download_song song_audio download returned None, falling back")
                    await self.loop.run_in_executor(None, song_audio_dl)
                    fpath = f"downloads/{title}.mp3"
                return fpath, direct

            elif video:
                if await is_on_off(1):
                    try:
                        downloaded_file = await download_song(link)
                        if downloaded_file is None:
                            print("download_song video download returned None, falling back")
                            downloaded_file = await self.loop.run_in_executor(None, video_dl)
                    except Exception as e:
                        print(f"Async video download failed, trying fallback: {e}")
                        downloaded_file = await self.loop.run_in_executor(None, video_dl)
                    direct = True
                else:
                    try:
                        proc = await asyncio.create_subprocess_exec()
                            "yt-dlp",
                            "--cookies", cookie_txt_file(),
                            "-g",
                            "-f", "best[height<=?720][width<=?1280]",
                            f"{link}",
                            stdout=asyncio.subprocess.PIPE,
 
