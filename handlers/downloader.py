import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from aiogram import Router, F
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from services.downloader import (
    download_media,
    download_audio,
    get_video_info,
    extract_first_url,
    clean_url_key,
    format_progress_bar,
    format_eta,
    format_speed,
    DownloadFailedError,
)
from services.cache import media_cache
from services.telegram_client import send_large_video, send_large_audio
from config import IS_RENDER

logger = logging.getLogger(__name__)
router = Router()

URL_SESSIONS: Dict[str, str] = {}

RENDER_YOUTUBE_MSG = (
    "⏳ <b>YouTube hozircha mavjud emas.</b>\n"
    "Iltimos, birozdan keyin qayta urinib ko‘ring. Instagram havolalari ishlayapti ✅"
)


def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def resolve_session_url(call: CallbackQuery, session_id: str) -> Optional[str]:
    """
    Sessiya xotirada bo'lmasa (bot qayta ishga tushgan yoki Render <-> lokal almashgan),
    havolani foydalanuvchining asl xabaridan tiklaydi.
    """
    url = URL_SESSIONS.get(session_id)
    if url:
        return url
    original = call.message.reply_to_message if call.message else None
    if original and original.text:
        url = extract_first_url(original.text)
        if url:
            URL_SESSIONS[session_id] = url
    return url


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Noma'lum"
    mins = seconds // 60
    secs = seconds % 60
    if mins > 0:
        return f"{mins} daqiqa {secs} soniya"
    return f"{secs} soniya"


def build_download_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """
    Video sifatlari (360p, 480p, 720p, 1080p) va MP3 Audio tugmasini yaratadi.
    """
    try:
        video_buttons = [
            InlineKeyboardButton(text="📹 360p", callback_data=f"dl:360:{session_id}", style="primary"),
            InlineKeyboardButton(text="📹 480p", callback_data=f"dl:480:{session_id}", style="primary"),
            InlineKeyboardButton(text="📹 720p (HD)", callback_data=f"dl:720:{session_id}", style="primary"),
            InlineKeyboardButton(text="📹 1080p (Full HD)", callback_data=f"dl:1080:{session_id}", style="primary"),
        ]
        audio_btn = [
            InlineKeyboardButton(text="🎵 MP3 Audio (Musiqa)", callback_data=f"dl_audio:{session_id}", style="success")
        ]
        return InlineKeyboardMarkup(inline_keyboard=[video_buttons[:2], video_buttons[2:], audio_btn])
    except Exception:
        video_buttons = [
            InlineKeyboardButton(text="📹 360p", callback_data=f"dl:360:{session_id}"),
            InlineKeyboardButton(text="📹 480p", callback_data=f"dl:480:{session_id}"),
            InlineKeyboardButton(text="📹 720p (HD)", callback_data=f"dl:720:{session_id}"),
            InlineKeyboardButton(text="📹 1080p (Full HD)", callback_data=f"dl:1080:{session_id}"),
        ]
        audio_btn = [
            InlineKeyboardButton(text="🎵 MP3 Audio (Musiqa)", callback_data=f"dl_audio:{session_id}")
        ]
        return InlineKeyboardMarkup(inline_keyboard=[video_buttons[:2], video_buttons[2:], audio_btn])


async def process_audio_download(
    url: str,
    target_chat_id: int,
    bot,
    status_msg: Message,
    reply_to_message_id: Optional[int] = None,
):
    """
    MP3 audioni yuklab olish, keshdan tekshirish va foydalanuvchiga audio qilib yuborish.
    """
    bot_info = await bot.get_me()
    cache_key = f"{clean_url_key(url)}_audio"

    # 1. Tezkor Kesh (0.1 soniyada yuborish)
    cached = media_cache.get(cache_key)
    if cached:
        logger.info(f"Audio keshdan topildi: {cache_key}")
        caption = f"🎵 <b>{cached['title']}</b>\n\n🤖 @{bot_info.username}"
        try:
            await bot.send_audio(
                chat_id=target_chat_id,
                audio=cached["file_id"],
                caption=caption,
                title=cached.get("title"),
                duration=cached.get("duration"),
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML"
            )
            try:
                await status_msg.delete()
            except Exception:
                pass
            return
        except Exception as e:
            logger.warning(f"Keshdagi audio bilan yuborishda ogohlantirish: {e}")

    # 2. Yuklash jarayoni
    try:
        await status_msg.edit_text(
            "🎵 <b>MP3 audio yuklanmoqda va tayyorlanmoqda, iltimos kuting...</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await bot.send_chat_action(
            chat_id=target_chat_id,
            action=ChatAction.UPLOAD_DOCUMENT
        )
    except Exception:
        pass

    loop = asyncio.get_running_loop()
    last_update_time = [0.0]
    last_percent = [-1.0]

    def on_progress(data: dict):
        now = time.time()
        percent = data.get("percent", 0.0)
        eta = data.get("eta")
        speed = data.get("speed")

        if (now - last_update_time[0] >= 2.0) and (abs(percent - last_percent[0]) >= 3.0 or eta is not None):
            last_update_time[0] = now
            last_percent[0] = percent

            bar = format_progress_bar(percent)
            eta_str = format_eta(eta)
            speed_str = format_speed(speed)

            text_lines = [
                "📥 <b>Audio yuklanmoqda (MP3)...</b>\n",
                f"📊 {bar}",
                f"⏱ <b>Qolgan vaqt:</b> {eta_str}",
            ]
            if speed_str:
                text_lines.append(f"🚀 <b>Tezlik:</b> {speed_str}")

            new_text = "\n".join(text_lines)

            async def safe_edit():
                try:
                    await status_msg.edit_text(new_text, parse_mode="HTML")
                except Exception:
                    pass

            asyncio.run_coroutine_threadsafe(safe_edit(), loop)

    downloaded_path: Optional[Path] = None
    thumb_path: Optional[Path] = None

    try:
        audio_info = await download_audio(url, progress_callback=on_progress)
        downloaded_path = audio_info["file_path"]
        thumb_path = audio_info.get("thumb_path")
        duration = audio_info.get("duration") or 0
        title = audio_info.get("title") or "Audio"
        uploader = audio_info.get("uploader") or "YouTube"
        file_size_mb = audio_info["file_size"] / (1024 * 1024)

        try:
            await status_msg.edit_text(
                f"🚀 <b>MP3 yuborilmoqda...</b> ({file_size_mb:.1f} MB)",
                parse_mode="HTML"
            )
        except Exception:
            pass

        caption = (
            f"🎵 <b>{title}</b>\n"
            f"👤 <b>Ijrochi:</b> {uploader}\n"
            f"💾 <b>Hajmi:</b> {file_size_mb:.1f} MB\n\n"
            f"🤖 @{bot_info.username}"
        )

        # 50 MB dan katta bo'lsa -> Telethon MTProto (2 GB gacha yaxlit fayl)
        if file_size_mb > 49.0:
            logger.info(f"Audio {file_size_mb:.1f} MB: Telethon MTProto orqali yuborilmoqda...")
            await send_large_audio(
                chat_id=target_chat_id,
                file_path=downloaded_path,
                caption=caption,
                title=title,
                performer=uploader,
                duration=duration,
                thumb_path=thumb_path
            )
        else:
            audio_input = FSInputFile(str(downloaded_path))
            thumbnail_input = FSInputFile(str(thumb_path)) if thumb_path and thumb_path.exists() else None
            sent_audio = await bot.send_audio(
                chat_id=target_chat_id,
                audio=audio_input,
                thumbnail=thumbnail_input,
                caption=caption,
                title=title,
                performer=uploader,
                duration=duration,
                reply_to_message_id=reply_to_message_id,
                parse_mode="HTML"
            )

            if sent_audio.audio and sent_audio.audio.file_id:
                media_cache.set(cache_key, sent_audio.audio.file_id, title, duration)

        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Audio yuklashda xato: {e}")
        err_text = str(e).lower()
        if IS_RENDER and is_youtube_url(url):
            friendly_msg = RENDER_YOUTUBE_MSG
        elif "unavailable" in err_text or "not available" in err_text or "deleted" in err_text:
            friendly_msg = "❌ <b>Ushbu video YouTube'da mavjud emas yoki muallif tomonidan o‘chirilgan!</b>"
        elif "private" in err_text:
            friendly_msg = "🔒 <b>Ushbu video yopiq (private) profilga tegishli.</b> Yuklab bo‘lmaydi."
        elif "sign in to confirm" in err_text:
            friendly_msg = "❌ <b>YouTube cheklovi:</b> Ushbu video uchun yosh chegarasi (18+) yoki avtorizatsiya talab qilinadi."
        else:
            friendly_msg = "❌ <b>Audioni yuklab bo‘lmadi.</b> Iltimos, boshqa havola bilan urinib ko‘ring."

        try:
            await status_msg.edit_text(friendly_msg, parse_mode="HTML")
        except Exception:
            pass

    finally:
        if downloaded_path and downloaded_path.exists():
            try:
                downloaded_path.unlink()
                logger.info(f"Audio fayl tozalandi: {downloaded_path}")
            except OSError as err:
                logger.error(f"Audio faylni tozalashda xatolik: {err}")
        if thumb_path and thumb_path.exists():
            try:
                thumb_path.unlink()
                logger.info(f"Audio thumbnail tozalandi: {thumb_path}")
            except OSError as err:
                logger.error(f"Audio thumbnailni tozalashda xatolik: {err}")


@router.message(Command("mp3", "audio"))
async def handle_audio_command(message: Message):
    """
    /mp3 <url> yoki /audio <url> buyrug'i orqali to'g'ridan-to'g'ri audioni yuklab olish.
    """
    url = extract_first_url(message.text)
    if not url:
        await message.reply(
            "🎵 <b>Videodan MP3 audio yuklash:</b>\n\n"
            "Menga YouTube yoki Instagram havolasini yuboring va <b>🎵 MP3 Audio</b> tugmasini bosing, "
            "yoki buyruq bilan birga havolani yuboring:\n"
            "<code>/mp3 https://youtube.com/watch?v=...</code>",
            parse_mode="HTML"
        )
        return

    status_msg = await message.reply("⚡️ <b>MP3 audio yuklanmoqda...</b>", parse_mode="HTML")
    await process_audio_download(
        url=url,
        target_chat_id=message.chat.id,
        bot=message.bot,
        status_msg=status_msg,
        reply_to_message_id=message.message_id
    )


@router.message(F.text)
async def handle_url_message(message: Message):
    url = extract_first_url(message.text)

    if not url:
        await message.reply(
            "⚠️ Iltimos, to'g'ri **Instagram** (Reels/Post) yoki **YouTube** (Shorts/Video) havolasini yuboring.\n\n"
            "Masalan:\n"
            "• `https://www.instagram.com/reel/...`\n"
            "• `https://youtube.com/shorts/...`",
            parse_mode="Markdown"
        )
        return

    session_id = uuid.uuid4().hex[:8]
    URL_SESSIONS[session_id] = url

    keyboard = build_download_keyboard(session_id)

    text = (
        "🎬 <b>Format va sifatni tanlang:</b>\n\n"
        "Videoni kerakli sifatda yoki <b>🎵 MP3 audio (musiqa)</b> formatida yuklab olish uchun tugmalardan birini bosing 👇"
    )

    sent_msg = await message.reply(text, parse_mode="HTML", reply_markup=keyboard)

    # Orqa fonda (background) video ma'lumotlarini tekshirib, xabarni chiroyli to'ldirib qo'yish
    async def update_info_bg():
        try:
            info = await get_video_info(url)
            title = info.get("title") or "Video"
            duration_str = format_duration(info.get("duration", 0))
            updated_text = (
                f"🎬 <b>{title}</b>\n"
                f"⏱ Davomiyligi: <b>{duration_str}</b>\n\n"
                f"Format va sifatlardan birini tanlang 👇"
            )
            await sent_msg.edit_text(updated_text, parse_mode="HTML", reply_markup=keyboard)
        except DownloadFailedError as err:
            if IS_RENDER and is_youtube_url(url):
                return  # Render'da YouTube xatolari bloklash sababli; video o'chirilgan deb noto'g'ri yozmaymiz
            err_msg = str(err).lower()
            if "unavailable" in err_msg or "not available" in err_msg:
                await sent_msg.edit_text("❌ <b>Ushbu video YouTube'da mavjud emas yoki muallif tomonidan o‘chirilgan!</b>", parse_mode="HTML")
            elif "private" in err_msg:
                await sent_msg.edit_text("🔒 <b>Ushbu video yopiq (private) profilga tegishli.</b> Yuklab bo‘lmaydi.", parse_mode="HTML")
        except Exception:
            pass

    asyncio.create_task(update_info_bg())


@router.callback_query(F.data.startswith("dl_audio:"))
async def handle_audio_choice(call: CallbackQuery):
    await call.answer()

    parts_data = call.data.split(":")
    session_id = parts_data[1]

    url = resolve_session_url(call, session_id)
    if not url:
        await call.message.edit_text("⚠️ Havola muddati tugagan. Iltimos, havolani qaytadan yuboring.")
        return

    await process_audio_download(
        url=url,
        target_chat_id=call.message.chat.id,
        bot=call.message.bot,
        status_msg=call.message
    )


@router.callback_query(F.data.startswith("dl:"))
async def handle_quality_choice(call: CallbackQuery):
    await call.answer()

    parts_data = call.data.split(":")
    if len(parts_data) < 3 or not parts_data[1].isdigit():
        return

    quality = int(parts_data[1])
    session_id = parts_data[2]

    url = resolve_session_url(call, session_id)
    if not url:
        await call.message.edit_text("⚠️ Havola muddati tugagan. Iltimos, havolani qaytadan yuboring.")
        return

    bot_info = await call.message.bot.get_me()
    cache_key = f"{clean_url_key(url)}_{quality}"

    # 1. Tezkor Kesh (0.2 soniyada yuborish)
    cached = media_cache.get(cache_key)
    if cached:
        logger.info(f"Video keshdan topildi: {cache_key}")
        caption = f"🎬 {cached['title']}\n📐 Sifat: {quality}p\n\n🤖 @{bot_info.username}"
        try:
            await call.message.answer_video(
                video=cached["file_id"],
                caption=caption,
                duration=cached.get("duration"),
                supports_streaming=True
            )
            await call.message.delete()
            return
        except Exception:
            pass

    # 2. Yuklash jarayoni
    status_msg = await call.message.edit_text(
        f"⚡️ <b>{quality}p</b> sifatda yuklanmoqda, iltimos kuting...",
        parse_mode="HTML"
    )

    await call.message.bot.send_chat_action(
        chat_id=call.message.chat.id,
        action=ChatAction.UPLOAD_VIDEO
    )

    loop = asyncio.get_running_loop()
    last_update_time = [0.0]
    last_percent = [-1.0]

    def on_progress(data: dict):
        now = time.time()
        percent = data.get("percent", 0.0)
        eta = data.get("eta")
        speed = data.get("speed")

        if (now - last_update_time[0] >= 2.0) and (abs(percent - last_percent[0]) >= 3.0 or eta is not None):
            last_update_time[0] = now
            last_percent[0] = percent

            bar = format_progress_bar(percent)
            eta_str = format_eta(eta)
            speed_str = format_speed(speed)

            text_lines = [
                f"📥 <b>Video yuklanmoqda ({quality}p)...</b>\n",
                f"📊 {bar}",
                f"⏱ <b>Qolgan vaqt:</b> {eta_str}",
            ]
            if speed_str:
                text_lines.append(f"🚀 <b>Tezlik:</b> {speed_str}")

            new_text = "\n".join(text_lines)

            async def safe_edit():
                try:
                    await status_msg.edit_text(new_text, parse_mode="HTML")
                except Exception:
                    pass

            asyncio.run_coroutine_threadsafe(safe_edit(), loop)

    downloaded_path: Optional[Path] = None
    thumb_path: Optional[Path] = None

    try:
        media_info = await download_media(url, target_height=quality, progress_callback=on_progress)
        downloaded_path = media_info["file_path"]
        thumb_path = media_info.get("thumb_path")
        duration = media_info.get("duration") or 0
        title = media_info.get("title") or "Video"
        actual_height = media_info.get("height") or quality
        actual_width = media_info.get("width") or 1280
        file_size_mb = media_info["file_size"] / (1024 * 1024)

        try:
            await status_msg.edit_text(
                f"🚀 <b>Video yuborilmoqda...</b> ({file_size_mb:.1f} MB, {actual_height}p)",
                parse_mode="HTML"
            )
        except Exception:
            pass

        caption = (
            f"🎬 {title}\n"
            f"📐 Sifat: {actual_height}p ({file_size_mb:.1f} MB)\n\n"
            f"🤖 @{bot_info.username}"
        )

        # AGAR VIDEO 50 MB DAN KATTA BO'LSA -> TELETHON MTPROTO (2 GB gacha yaxlit video)
        if file_size_mb > 49.0:
            logger.info(f"Video {file_size_mb:.1f} MB: Telethon MTProto orqali bitta yaxlit video yuborilmoqda...")
            await send_large_video(
                chat_id=call.message.chat.id,
                file_path=downloaded_path,
                caption=caption,
                duration=duration,
                width=actual_width,
                height=actual_height,
                thumb_path=thumb_path
            )
        else:
            # AGAR VIDEO <= 50 MB BO'LSA -> AIOGRAM ORQALI TEZKOR YUBORISH
            video_input = FSInputFile(str(downloaded_path))
            thumbnail_input = FSInputFile(str(thumb_path)) if thumb_path and thumb_path.exists() else None
            sent_msg = await call.message.answer_video(
                video=video_input,
                thumbnail=thumbnail_input,
                caption=caption,
                duration=duration,
                width=actual_width,
                height=actual_height,
                supports_streaming=True
            )

            if sent_msg.video and sent_msg.video.file_id:
                media_cache.set(cache_key, sent_msg.video.file_id, title, duration)

        # Status xabarini tozalash
        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Yuklashda xato: {e}")
        err_text = str(e).lower()
        if IS_RENDER and is_youtube_url(url):
            friendly_msg = RENDER_YOUTUBE_MSG
        elif "unavailable" in err_text or "not available" in err_text or "deleted" in err_text:
            friendly_msg = "❌ <b>Ushbu video YouTube'da mavjud emas yoki muallif tomonidan o‘chirilgan!</b>"
        elif "private" in err_text:
            friendly_msg = "🔒 <b>Ushbu video yopiq (private) profilga tegishli.</b> Yuklab bo‘lmaydi."
        elif "sign in to confirm" in err_text:
            friendly_msg = "❌ <b>YouTube cheklovi:</b> Ushbu video uchun yosh chegarasi (18+) yoki avtorizatsiya talab qilinadi."
        else:
            friendly_msg = "❌ <b>Videoni yuklab bo‘lmadi.</b> Iltimos, boshqa sifatni tanlang yoki keyinroq qayta urinib ko‘ring."

        try:
            await status_msg.edit_text(friendly_msg, parse_mode="HTML")
        except Exception:
            pass

    finally:
        # Faylni va thumbnailni diskdan xavfsiz tozalash
        if downloaded_path and downloaded_path.exists():
            try:
                downloaded_path.unlink()
                logger.info(f"Fayl tozalandi: {downloaded_path}")
            except OSError as err:
                logger.error(f"Faylni tozalashda xatolik: {err}")
        if thumb_path and thumb_path.exists():
            try:
                thumb_path.unlink()
                logger.info(f"Thumbnail tozalandi: {thumb_path}")
            except OSError as err:
                logger.error(f"Thumbnailni tozalashda xatolik: {err}")
