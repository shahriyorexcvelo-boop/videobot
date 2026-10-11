import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN aniqlanmadi! Iltimos, .env faylida BOT_TOKEN ni ko'rsating.")

API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "").strip()

DOWNLOAD_DIR: Path = BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

PORT: int = int(os.getenv("PORT", "8080"))

# Render.com o'zi avtomatik RENDER=true o'zgaruvchisini o'rnatadi
IS_RENDER: bool = os.getenv("RENDER", "").lower() == "true"

# Render <-> Lokal navbat almashish (handoff) sozlamalari
# RENDER_URL faqat lokal .env da kerak (masalan: https://video-telegram-bot.onrender.com)
RENDER_URL: str = os.getenv("RENDER_URL", "").strip()
# Ikkala joyda ham (Render env va lokal .env) bir xil bo'lishi shart
HANDOFF_SECRET: str = os.getenv("HANDOFF_SECRET", "").strip()

# MTProto orqali maksimal fayl hajmi: 2 GB (2048 MB)
MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024
