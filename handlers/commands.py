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
        "📖 <b>Botdan foydalanish qo'llanmasi:</b>\n\n"
        "1. <b>Instagram</b> yoki <b>YouTube</b> ilovasidan video havolasini (link) nusxalang.\n"
        "2. Havolani botga yuboring.\n"
        "3. Kerakli sifat tugmasini bosing (<b>360p, 480p, 720p, 1080p</b>).\n"
        "4. Bot videoni bir zumda yuklab, sizga taqdim etadi.\n\n"
        "⚡️ <b>Imkoniyatlar:</b>\n"
        "• <b>2 GB gacha</b> katta videolarni bitta yaxlit video qilib yuboradi.\n"
        "• Barcha telefonlarda (iPhone va Android) to'xtovsiz o'ynaydi.\n"
        "• Oldin yuklangan videolar keshdan 0.1 soniyada keladi."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("about"))
async def cmd_about(message: Message):
    """
    /about komandasi uchun handler.
    """
    text = (
        "🤖 <b>VIDEO FAST Bot haqida:</b>\n\n"
        "Ushbu bot ijtimoiy tarmoqlardan yuqori sifatli videolarni tezkor yuklash uchun mo'ljallangan.\n\n"
        "✨ <b>Xususiyatlari:</b>\n"
        "• 📥 <b>Instagram</b>: Reels, Stories, Post\n"
        "• 🎥 <b>YouTube</b>: Shorts va to'liq videolar\n"
        "• 💎 <b>Full HD</b> (1080p gacha) sifat\n"
        "• 🚀 <b>Tezkor yuklash va 24/7 rejim</b>\n\n"
        "<i>Havolani yuboring va sinab ko'ring!</i>"
    )
    await message.answer(text, parse_mode="HTML")
