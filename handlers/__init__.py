from aiogram import Router
from .commands import router as commands_router
from .downloader import router as downloader_router

main_router = Router()

# Handlerlar tartibi: avval komandalar (/start, /help), keyin matnli havolalar
main_router.include_router(commands_router)
main_router.include_router(downloader_router)

__all__ = ["main_router"]
