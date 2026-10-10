import logging
from pathlib import Path
from typing import Optional, Callable

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeVideo
from config import API_ID, API_HASH, BOT_TOKEN, BASE_DIR

logger = logging.getLogger(__name__)

SESSION_PATH = str(BASE_DIR / "bot_telethon")
telethon_client: Optional[TelegramClient] = None


async def get_telethon_client() -> TelegramClient:
    """
    Telethon bot mijozini qaytaradi (bir marta initsializatsiya qilinadi).
    MTProto orqali 2 GB gacha fayllarni to'g'ridan-to'g'ri yuboradi.
    """
    global telethon_client
    if telethon_client is None:
        if not API_ID or not API_HASH:
            raise ValueError("API_ID yoki API_HASH sozlanmagan!")

        telethon_client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        await telethon_client.start(bot_token=BOT_TOKEN)
        logger.info("Telethon 2 GB uploader mijozi muvaffaqiyatli ishga tushdi!")

    return telethon_client


async def send_large_video(
    chat_id: int,
    file_path: Path,
    caption: str,
    duration: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    thumb_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
):
    """
    Videoni telefonlarda va barcha qurilmalarda 100% ochiladigan qilib,
    video atributlari (DocumentAttributeVideo) va thumbnail bilan yuboradi.
    """
    client = await get_telethon_client()

    logger.info(f"Telethon orqali video yuborilmoqda: {file_path.name} ({width}x{height}, duration: {duration}s)")

    # Telegram mobil ilovasi videoni to'g'ri o'ynatishi uchun zarur video atributlari
    video_attributes = [
        DocumentAttributeVideo(
            duration=int(duration or 0),
            w=int(width or 1280),
            h=int(height or 720),
            supports_streaming=True
        )
    ]

    thumb_file = str(thumb_path) if thumb_path and thumb_path.exists() else None

    message = await client.send_file(
        entity=chat_id,
        file=file_path,
        caption=caption,
        thumb=thumb_file,
        supports_streaming=True,
        attributes=video_attributes,
        progress_callback=progress_callback
    )

    return message
