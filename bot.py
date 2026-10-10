import asyncio
import logging
import sys
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN, PORT
from handlers import main_router
from services.telegram_client import get_telethon_client

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def handle_health_check(request):
    """
    Render.com 24/7 Health Check va UptimeRobot uchun web endpoint.
    Render bepul tarifida uxlab qolmasligi uchun doimiy 200 OK qaytaradi.
    """
    return web.json_response({
        "status": "online",
        "service": "VIDEO FAST Bot",
        "mtproto_2gb": True
    })


async def start_web_server():
    """
    Render.com talab qiladigan fon web serverini ishga tushiradi.
    """
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Render.com Web Server {PORT}-portda muvaffaqiyatli ishga tushdi (24/7 rejim)!")


async def setup_bot_commands(bot: Bot):
    """
    Telegram chat oynasidagi 'Menu' tugmasi va komandalar ro'yxatini sozlaydi.
    """
    commands = [
        BotCommand(command="start", description="🚀 Botni ishga tushirish"),
        BotCommand(command="help", description="📖 Qo'llanma va yordam"),
        BotCommand(command="about", description="ℹ️ Bot haqida ma'lumot"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot Menu buyruqlari muvaffaqiyatli o'rnatildi (/start, /help, /about)!")


async def main():
    logger.info("Bot tizimi ishga tushirilmoqda...")

    # 1. Render.com uchun 24/7 web serverni yoqish
    await start_web_server()

    # 2. Telethon (2 GB MTProto uploader) mijozini oldindan ishga tushirish
    try:
        await get_telethon_client()
    except Exception as e:
        logger.warning(f"Telethon mijozini oldindan ishga tushirishda ogohlantirish: {e}")

    # 3. Aiogram Bot va Dispatcher yaratish
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(main_router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        bot_info = await bot.get_me()
        logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} (ID: {bot_info.id})")

        # Telegram 'Menu' tugmasi buyruqlarini ro'yxatdan o'tkazish
        await setup_bot_commands(bot)

        # Long-polling orqali yangilanishlarni qabul qilish
        await dp.start_polling(bot)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi!")
    finally:
        await bot.session.close()
        logger.info("Bot sessiyasi yopildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur yakunlandi.")
