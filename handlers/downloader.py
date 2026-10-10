import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any

from aiogram import Router, F
from aiogram.enums import ChatAction
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from services.downloader import (
    download_media,
    get_video_info,
    extract_first_url,
    clean_url_key,
    format_progress_bar,
    format_eta,
    format_speed,
    DownloadFailedError,
)
from services.cache import media_cache
from services.telegram_client import send_large_video

logger = logging.getLogger(__name__)
router = Router()

URL_SESSIONS: Dict[str, str] = {}


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Noma'lum"
    mins = seconds // 60
    secs = seconds % 60
    if mins > 0:
        return f"{mins} daqiqa {secs} soniya"
    return f"{secs} soniya"


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

    # Tugmalarni BIR LAHZADA (0.05 soniyada) bir xil chiroyli rangda chiqarish
    buttons = [
        InlineKeyboardButton(text="📹 360p", callback_data=f"dl:360:{session_id}", style="primary"),
        InlineKeyboardButton(text="📹 480p", callback_data=f"dl:480:{session_id}", style="primary"),
        InlineKeyboardButton(text="📹 720p (HD)", callback_data=f"dl:720:{session_id}", style="primary"),
        InlineKeyboardButton(text="📹 1080p (Full HD)", callback_data=f"dl:1080:{session_id}", style="primary"),
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons[:2], buttons[2:]])

    text = (
        "🎬 <b>Video sifatini tanlang:</b>\n\n"
        "Yuklab olmoqchi bo'lgan sifat tugmasini bosing 👇"
    )

    try:
        sent_msg = await message.reply(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        # Style qo'llab-quvvatlanmagan taqdirda oddiy tugmalar bilan
        clean_buttons = [InlineKeyboardButton(text=b.text, callback_data=b.callback_data) for b in buttons]
        clean_keyboard = InlineKeyboardMarkup(inline_keyboard=[clean_buttons[:2], clean_buttons[2:]])
        sent_msg = await message.reply(text, parse_mode="HTML", reply_markup=clean_keyboard)

    # Orqa fonda (background) video ma'lumotlarini tekshirib, xabarni chiroyli to'ldirib qo'yish
    async def update_info_bg():
        try:
            info = await get_video_info(url)
            title = info.get("title") or "Video"
            duration_str = format_duration(info.get("duration", 0))
            updated_text = (
                f"🎬 <b>{title}</b>\n"
                f"⏱ Davomiyligi: <b>{duration_str}</b>\n\n"
                f"Sifatlardan birini tanlang 👇"
            )
            await sent_msg.edit_text(updated_text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass

    asyncio.create_task(update_info_bg())


@router.callback_query(F.data.startswith("dl:"))
async def handle_quality_choice(call: CallbackQuery):
    await call.answer()

    parts_data = call.data.split(":")
    quality = int(parts_data[1])
    session_id = parts_data[2]

    url = URL_SESSIONS.get(session_id)
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

    downloaded_path: Path | None = None
    thumb_path: Path | None = None

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
        try:
            await status_msg.edit_text(f"❌ Videoni yuborishda xatolik yuz berdi: {e}")
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
