from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    /start komandasi uchun handler.
    Foydalanuvchiga bot nima qila olishi haqida ma'lumot beradi.
    """
    text = (
        f"Assalomu alaykum, {message.from_user.full_name}! 👋\n\n"
        "Men **Instagram** va **YouTube** tarmoqlaridan video yuklovchi botman.\n\n"
        "Menga quyidagilardan birining havolasini yuboring:\n"
        "▫️ **Instagram**: Reels, Post yoki Video havolasi\n"
        "▫️ **YouTube**: Shorts yoki oddiy video havolasi\n\n"
        "💡 *Shunchaki havolani shu yerga yuboring, men uni videoga aylantirib beraman!*"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    /help komandasi uchun handler.
    """
    text = (
        "ℹ️ **Qo'llanma:**\n\n"
        "1. Instagram yoki YouTube ilovasidan kerakli videoning havolasini nusxalang.\n"
        "2. Havolani ushbu botga xabar sifatida yuboring.\n"
        "3. Bot videoni yuklab olib, sizga yuboradi.\n\n"
        "⚠️ **Eslatma:**\n"
        "• Telegram boti orqali yuboriladigan videolarning maksimal hajmi 50 MB.\n"
        "• Yopiq (private) profillardagi videolarni yuklab bo'lmaydi."
    )
    await message.answer(text, parse_mode="Markdown")
