import asyncio
import logging
import sys
import os

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN, PORT, IS_RENDER, RENDER_URL, HANDOFF_SECRET
from handlers import main_router
from services.telegram_client import get_telethon_client
from services import handoff

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


async def start_web_server(supervisor=None):
    """
    Render.com talab qiladigan fon web serverini ishga tushiradi.
    """
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)
    if supervisor is not None:
        supervisor.register_routes(app)

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
        BotCommand(command="mp3", description="🎵 MP3 audio yuklash"),
        BotCommand(command="help", description="📖 Qo'llanma va yordam"),
        BotCommand(command="about", description="ℹ️ Bot haqida ma'lumot"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot Menu buyruqlari muvaffaqiyatli o'rnatildi (/start, /mp3, /help, /about)!")


async def main():
    logger.info("Bot tizimi ishga tushirilmoqda...")

    # Aiogram Bot va Dispatcher yaratish
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(main_router)

    render_supervised = IS_RENDER and bool(HANDOFF_SECRET)
    local_handoff = (not IS_RENDER) and bool(RENDER_URL) and bool(HANDOFF_SECRET)
    supervisor = handoff.RenderPollingSupervisor(dp, bot) if render_supervised else None

    # 1. Render.com uchun 24/7 web serverni yoqish (Render'da /lease endpoint bilan)
    await start_web_server(supervisor)

    # 2. Lokal rejim: Render'ni vaqtincha to'xtatib turish
    http_session: aiohttp.ClientSession | None = None
    heartbeat_task: asyncio.Task | None = None
    if local_handoff:
        http_session = aiohttp.ClientSession()
        await handoff.acquire_from_render(http_session)
        heartbeat_task = asyncio.create_task(handoff.heartbeat_loop(http_session))

    # 3. Telethon (2 GB MTProto uploader) mijozini oldindan ishga tushirish
    try:
        await get_telethon_client()
    except Exception as e:
        logger.warning(f"Telethon mijozini oldindan ishga tushirishda ogohlantirish: {e}")

    try:
        # Navbat almashishda kelgan xabarlar yo'qolmasligi uchun lokalda ularni o'chirmaymiz
        await bot.delete_webhook(drop_pending_updates=not local_handoff)
        bot_info = await bot.get_me()
        logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} (ID: {bot_info.id})")

        # Telegram 'Menu' tugmasi buyruqlarini ro'yxatdan o'tkazish
        await setup_bot_commands(bot)

        if supervisor is not None:
            # Render: polling lokal bot holatiga qarab yoqiladi/o'chiriladi
            await supervisor.run()
        else:
            # Long-polling orqali yangilanishlarni qabul qilish
            await dp.start_polling(bot)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi!")
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        if http_session:
            await handoff.release_to_render(http_session)
            await http_session.close()
        await bot.session.close()
        logger.info("Bot sessiyasi yopildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur yakunlandi.")
