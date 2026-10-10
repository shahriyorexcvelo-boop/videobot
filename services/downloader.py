import asyncio
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse, parse_qs

import yt_dlp
from config import DOWNLOAD_DIR

logger = logging.getLogger(__name__)


def get_ffmpeg_binary() -> Optional[str]:
    """
    Tizimdagi ffmpeg yo'lini topadi yoki imageio_ffmpeg orqali o'rnatilganini oladi.
    """
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        logger.warning(f"imageio_ffmpeg orqali ffmpeg topilmadi: {e}")
        return None


def get_node_binary() -> Optional[str]:
    """
    Tizimdagi node (NodeJS) yo'lini topadi (YouTube JS challenge larini yechish uchun).
    """
    return shutil.which("node") or ("/opt/homebrew/bin/node" if os.path.exists("/opt/homebrew/bin/node") else None)


class DownloaderException(Exception):
    """Downloader moduli uchun asosiy xatolik klassi."""
    pass


class DownloadFailedError(DownloaderException):
    """Videoni yuklab olishda muammo yuzaga kelganda chaqiriladi."""
    pass


SUPPORTED_URL_PATTERN = re.compile(
    r"(https?://(?:www\.)?(?:instagram\.com/(?:p|reel|reels|tv|share)/[^\s]+|"
    r"(?:youtube\.com/(?:watch\?[^\s]+|shorts/[^\s]+|embed/[^\s]+|v/[^\s]+)|youtu\.be/[^\s]+)))",
    re.IGNORECASE
)


def extract_first_url(text: str) -> Optional[str]:
    """
    Xabar matni ichidan birinchi qo'llab-quvvatlanadigan URL havolasini ajratib oladi.
    """
    if not text:
        return None
    match = SUPPORTED_URL_PATTERN.search(text)
    if not match:
        return None
    url = match.group(1).strip()
    return re.sub(r"[,\.\)>]+$", "", url)


def normalize_url(url: str) -> str:
    """
    YouTube Shorts va qisqa havolalarni to'liq watch formatiga keltiradi.
    Bu YouTube'ning visionos va bot blokirovkalarini oldini oladi.
    """
    try:
        if "/shorts/" in url:
            short_id = url.split("/shorts/")[1].split("?")[0].split("/")[0]
            return f"https://www.youtube.com/watch?v={short_id}"
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0].split("/")[0]
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        pass
    return url


def is_supported_url(url: str) -> bool:
    if not url:
        return False
    return bool(SUPPORTED_URL_PATTERN.search(url))


def clean_url_key(url: str) -> str:
    """
    Kesh uchun yagona identifikator yaratadi.
    """
    try:
        parsed = urlparse(url)
        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/")
            return f"yt:{video_id}"
        if "youtube.com" in parsed.netloc:
            if "/shorts/" in parsed.path:
                short_id = parsed.path.split("/shorts/")[1].split("/")[0]
                return f"yt:{short_id}"
            qs = parse_qs(parsed.query)
            if "v" in qs:
                return f"yt:{qs['v'][0]}"
        if "instagram.com" in parsed.netloc:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("p", "reel", "reels", "tv"):
                return f"ig:{parts[1]}"
    except Exception:
        pass
    return url.split("?")[0]


def format_progress_bar(percent: float, length: int = 10) -> str:
    filled = int(length * (percent / 100.0))
    filled = max(0, min(length, filled))
    bar = "▰" * filled + "▱" * (length - filled)
    return f"[{bar}] {percent:.1f}%"


def format_eta(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "hisoblanmoqda..."
    secs = int(seconds)
    if secs < 60:
        return f"~{secs} soniya"
    mins = secs // 60
    rem_secs = secs % 60
    return f"~{mins} daq {rem_secs} son"


def format_speed(speed: Optional[float]) -> str:
    if not speed or speed <= 0:
        return ""
    if speed >= 1024 * 1024:
        return f"{speed / (1024 * 1024):.1f} MB/s"
    return f"{speed / 1024:.0f} KB/s"


def _build_base_ydl_opts() -> Dict[str, Any]:
    """
    YouTube va Instagram uchun eng xavfsiz va barqaror umumiy parametrlar.
    """
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "check_formats": False,
        "extractor_retries": 1,
        "file_access_retries": 1,
        "fragment_retries": 2,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "android_vr"],
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    }

    node_bin = get_node_binary()
    if node_bin:
        opts["js_runtimes"] = {"node": {"path": node_bin}}

    return opts


def _sync_get_info(url: str) -> Dict[str, Any]:
    """
    Videoni yuklamasdan ma'lumotlari va haqiqatda mavjud sifatlarini aniqlaydi.
    """
    clean_url = normalize_url(url)
    ydl_opts = _build_base_ydl_opts()
    ydl_opts.update({
        "skip_download": True,
        "extract_flat": "in_playlist",
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise DownloadFailedError("Video ma'lumotlarini olib bo'lmadi.")

            # Videoda mavjud bo'lgan video balandliklarini aniqlash
            formats = info.get("formats", [])
            heights = {f.get("height") for f in formats if f.get("height") and f.get("vcodec") != "none"}

            candidate_qualities = [360, 480, 720, 1080]
            available_qualities = [cq for cq in candidate_qualities if any(abs(h - cq) <= 20 for h in heights)]

            if not available_qualities and heights:
                available_qualities = sorted(list(heights))[:4]
            elif not available_qualities:
                available_qualities = [720]

            return {
                "id": info.get("id"),
                "title": info.get("title") or "Video",
                "duration": info.get("duration") or 0,
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
                "qualities": available_qualities,
                "url": clean_url,
            }
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp extract xatoligi: {e}")
        raise DownloadFailedError(f"Video ma'lumotlarini olib bo'lmadi: {e}")
    except Exception as e:
        logger.exception(f"Xatolik: {e}")
        raise DownloadFailedError(f"Xatolik: {e}")


async def get_video_info(url: str) -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_get_info, url)


def process_video_for_mobile(file_path: Path) -> Dict[str, Any]:
    """
    Videoni barcha telefonlarda (iPhone va Android) 100% o'ynaydigan holatga keltiradi:
    - Codec: H.264 (avc1) + AAC audio + yuv420p
    - Faststart (moov atom fayl boshida, to'g'ridan-to'g'ri oqimli ijro)
    - Thumbnail (.jpg muqova rasmi yaratish)
    - Aniq davomiylik (duration), kenglik (width) va balandlik (height) ni aniqlash
    """
    ffmpeg_exe = get_ffmpeg_binary()
    if not ffmpeg_exe:
        logger.warning("ffmpeg topilmadi, videoni qayta ishlash o'tkazib yuborildi.")
        return {
            "file_path": file_path,
            "thumb_path": None,
            "file_size": file_path.stat().st_size,
            "duration": 0,
            "width": 1280,
            "height": 720,
        }

    # 1. Video oqimlarini tekshirish
    cmd = [ffmpeg_exe, "-i", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stderr

    duration = 0
    dur_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', out)
    if dur_match:
        h, m, s = dur_match.groups()
        duration = int(int(h) * 3600 + int(m) * 60 + float(s))

    width, height = 1280, 720
    vcodec = "unknown"
    pix_fmt = "unknown"
    for line in out.splitlines():
        if "Stream #" in line and "Video:" in line:
            parts = line.split("Video:")[1]
            tokens = [t.strip(",") for t in parts.split()]
            if tokens:
                vcodec = tokens[0].lower()
            dim_match = re.search(r'(\d{2,5})x(\d{2,5})', parts)
            if dim_match:
                width = int(dim_match.group(1))
                height = int(dim_match.group(2))
            pix_match = re.search(r'(yuv\w+|rgb\w+)', parts)
            if pix_match:
                pix_fmt = pix_match.group(1)
            break

    acodec = "unknown"
    for line in out.splitlines():
        if "Stream #" in line and "Audio:" in line:
            parts = line.split("Audio:")[1]
            tokens = [t.strip(",") for t in parts.split()]
            if tokens:
                acodec = tokens[0].lower()
            break

    is_h264 = ("h264" in vcodec or "avc" in vcodec) and ("yuv420p" in pix_fmt)
    is_aac = "aac" in acodec or "mp4a" in acodec or acodec == "unknown"

    current_file = file_path

    # 2. Agar video telefonga to'g'ri kelmaydigan bo'lsa (VP9, AV1, Opus, 10-bit HDR):
    if not (is_h264 and is_aac):
        logger.info(f"Video mobil formatga moslashtirilmoqda (H.264/AAC ga transcode): {vcodec}/{acodec}")
        temp_transcoded = file_path.with_name(f"opt_{file_path.name}")
        trans_cmd = [
            ffmpeg_exe, "-y", "-i", str(file_path),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(temp_transcoded)
        ]
        trans_res = subprocess.run(trans_cmd, capture_output=True, text=True)
        if trans_res.returncode == 0 and temp_transcoded.exists():
            file_path.unlink(missing_ok=True)
            temp_transcoded.rename(file_path)
            current_file = file_path
        else:
            logger.error(f"Transcoding xatosi: {trans_res.stderr}")
    else:
        # H264 va AAC bo'lsa ham faststart (moov atom oldinda) qo'shilganiga 100% ishonch hosil qilish
        temp_fast = file_path.with_name(f"fast_{file_path.name}")
        fast_cmd = [
            ffmpeg_exe, "-y", "-i", str(file_path),
            "-c", "copy",
            "-movflags", "+faststart",
            str(temp_fast)
        ]
        fast_res = subprocess.run(fast_cmd, capture_output=True, text=True)
        if fast_res.returncode == 0 and temp_fast.exists():
            file_path.unlink(missing_ok=True)
            temp_fast.rename(file_path)
            current_file = file_path

    # 3. Telefonlar uchun sifatli Thumbnail (muqova rasmi) tayyorlash
    thumb_path = file_path.with_suffix(".thumb.jpg")
    ss_time = "00:00:01" if duration >= 2 else "00:00:00.500"
    thumb_cmd = [
        ffmpeg_exe, "-y", "-ss", ss_time, "-i", str(current_file),
        "-vframes", "1",
        "-vf", "scale=320:-2",
        "-q:v", "2",
        str(thumb_path)
    ]
    subprocess.run(thumb_cmd, capture_output=True)

    return {
        "file_path": current_file,
        "thumb_path": thumb_path if thumb_path.exists() else None,
        "duration": duration,
        "width": width,
        "height": height,
        "file_size": current_file.stat().st_size
    }


def _sync_download(
    url: str,
    target_height: int = 1080,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Foydalanuvchi tanlagan aniq sifatda videoni yuklab oladi.
    """
    clean_url = normalize_url(url)
    file_id = uuid.uuid4().hex[:10]
    output_template = str(DOWNLOAD_DIR / f"{file_id}_%(id)s.%(ext)s")

    ffmpeg_path = get_ffmpeg_binary()

    def ytdl_progress_hook(d: Dict[str, Any]):
        if progress_callback and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total * 100) if total > 0 else 0.0
            eta = d.get("eta")
            speed = d.get("speed")
            progress_callback({
                "status": "downloading",
                "percent": percent,
                "eta": eta,
                "speed": speed,
                "downloaded": downloaded,
                "total": total,
            })

    format_selector = (
        f"bestvideo[height={target_height}][vcodec^=avc][ext=mp4]+bestaudio[acodec^=mp4a]/"
        f"bestvideo[height={target_height}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
        f"bestvideo[height={target_height}][vcodec^=avc]+bestaudio/"
        f"bestvideo[height<={target_height}][vcodec^=avc][ext=mp4]+bestaudio[acodec^=mp4a]/"
        f"bestvideo[height<={target_height}][vcodec^=avc]+bestaudio/"
        f"bestvideo[height<={target_height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={target_height}]+bestaudio/"
        f"best[height<={target_height}][vcodec^=avc][ext=mp4]/"
        f"best[height<={target_height}][ext=mp4]/"
        f"best[height<={target_height}]/"
        "best"
    )

    ydl_opts = _build_base_ydl_opts()
    ydl_opts.update({
        "outtmpl": output_template,
        "progress_hooks": [ytdl_progress_hook],
    })

    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = ffmpeg_path
        ydl_opts["format"] = format_selector
        ydl_opts["merge_output_format"] = "mp4"
        ydl_opts["postprocessor_args"] = ["-movflags", "+faststart"]
    else:
        ydl_opts["format"] = f"best[height<={target_height}][ext=mp4]/best[ext=mp4]/best"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                raise DownloadFailedError("Video ma'lumotlarini olib bo'lmadi.")

            downloaded_file = None
            if "requested_downloads" in info and info["requested_downloads"]:
                downloaded_file = info["requested_downloads"][0].get("filepath")
            
            if not downloaded_file or not os.path.exists(downloaded_file):
                downloaded_file = ydl.prepare_filename(info)
                base_name = os.path.splitext(downloaded_file)[0]
                mp4_file = f"{base_name}.mp4"
                if os.path.exists(mp4_file):
                    downloaded_file = mp4_file

            if not downloaded_file or not os.path.exists(downloaded_file):
                raise DownloadFailedError("Video fayli muvaffaqiyatli yuklab olinmadi.")

            processed = process_video_for_mobile(Path(downloaded_file))
            return {
                "file_path": processed["file_path"],
                "thumb_path": processed.get("thumb_path"),
                "file_size": processed["file_size"],
                "title": info.get("title") or "Video",
                "duration": processed["duration"] or info.get("duration") or 0,
                "width": processed["width"] or info.get("width") or 1280,
                "height": processed["height"] or info.get("height") or target_height,
                "uploader": info.get("uploader"),
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        logger.warning(f"yt-dlp birlamchi yuklash xatosi: {error_msg}. Zaxira mobil mijoz bilan qayta urinilmoqda...")
        # Zaxira urinish: to'g'ridan-to'g'ri android/ios orqali 'best' formatida
        try:
            fallback_opts = _build_base_ydl_opts()
            fallback_opts.update({
                "outtmpl": output_template,
                "progress_hooks": [ytdl_progress_hook],
                "format": f"best[height<={target_height}]/best",
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "android_vr"],
                    }
                },
            })
            if ffmpeg_path:
                fallback_opts["ffmpeg_location"] = ffmpeg_path
                fallback_opts["merge_output_format"] = "mp4"

            with yt_dlp.YoutubeDL(fallback_opts) as ydl_fb:
                info = ydl_fb.extract_info(clean_url, download=True)
                downloaded_file = None
                if info and "requested_downloads" in info and info["requested_downloads"]:
                    downloaded_file = info["requested_downloads"][0].get("filepath")
                if not downloaded_file or not os.path.exists(downloaded_file):
                    downloaded_file = ydl_fb.prepare_filename(info)
                    base_name = os.path.splitext(downloaded_file)[0]
                    mp4_file = f"{base_name}.mp4"
                    if os.path.exists(mp4_file):
                        downloaded_file = mp4_file

                if downloaded_file and os.path.exists(downloaded_file):
                    processed = process_video_for_mobile(Path(downloaded_file))
                    return {
                        "file_path": processed["file_path"],
                        "thumb_path": processed.get("thumb_path"),
                        "file_size": processed["file_size"],
                        "title": info.get("title") or "Video",
                        "duration": processed["duration"] or info.get("duration") or 0,
                        "width": processed["width"] or info.get("width") or 1280,
                        "height": processed["height"] or info.get("height") or target_height,
                        "uploader": info.get("uploader"),
                    }
        except Exception as fb_err:
            logger.error(f"Zaxira usul ham xato berdi: {fb_err}")

        raise DownloadFailedError(f"Yuklab olishda xatolik yuz berdi: {error_msg}")
    except DownloaderException:
        raise
    except Exception as e:
        logger.exception(f"Kutilmagan xatolik: {e}")
        raise DownloadFailedError(f"Kutilmagan xatolik: {e}")


async def download_media(
    url: str,
    target_height: int = 1080,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_download, url, target_height, progress_callback)
