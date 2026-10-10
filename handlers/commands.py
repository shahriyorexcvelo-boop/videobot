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
        "Men **Instagram** va **YouTube** tarmoqlaridan **video** va **MP3 audio** yuklovchi botman.\n\n"
        "Menga quyidagilardan birining havolasini yuboring:\n"
        "▫️ **YouTube**: Shorts yoki to'liq video havolasi\n"
        "▫️ **Instagram**: Reels, Post yoki Video havolasi\n\n"
        "💡 *Shunchaki havolani shu yerga yuboring, kerakli sifat (360p - 1080p) yoki 🎵 MP3 Audio (Musiqa) tugmasini tanlang!*"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    /help komandasi uchun handler.
    """
    text = (
        "📖 <b>Botdan foydalanish qo'llanmasi:</b>\n\n"
        "1. <b>YouTube</b> yoki <b>Instagram</b> ilovasidan video havolasini nusxalang.\n"
        "2. Havolani botga yuboring.\n"
        "3. Kerakli formatni tanlang:\n"
        "   • 📹 <b>Video sifatlari:</b> 360p, 480p, 720p, 1080p\n"
        "   • 🎵 <b>MP3 Audio:</b> Videodan faqat musiqani/audioni ajratib olish\n"
        "4. Bot bir zumda faylni yuklab, sizga taqdim etadi.\n\n"
        "⚡️ <b>Qo'shimcha imkoniyatlar:</b>\n"
        "• <code>/mp3 &lt;havola&gt;</code> – to'g'ridan-to'g'ri MP3 audio formatida yuklab olish.\n"
        "• <b>2 GB gacha</b> katta hajmdagi audio va videolarni qo'llab-quvvatlaydi.\n"
        "• Muqova rasmi (cover) va ijrochi nomi to'liq ko'rsatiladi.\n"
        "• Oldin yuklangan fayllar keshdan 0.1 soniyada keladi."
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("about"))
async def cmd_about(message: Message):
    """
    /about komandasi uchun handler.
    """
    text = (
        "🤖 <b>VIDEO & AUDIO FAST Bot haqida:</b>\n\n"
        "Ushbu bot ijtimoiy tarmoqlardan yuqori sifatli video va MP3 musiqalarni tezkor yuklash uchun mo'ljallangan.\n\n"
        "✨ <b>Xususiyatlari:</b>\n"
        "• 🎵 <b>MP3 Audio</b>: Yuqori sifatli 192 kbps audio konvertatsiya\n"
        "• 🎥 <b>YouTube</b>: Shorts va to'liq videolar\n"
        "• 📥 <b>Instagram</b>: Reels, Stories, Post\n"
        "• 💎 <b>Full HD</b> (1080p gacha) sifat\n"
        "• 🚀 <b>Tezkor yuklash va 24/7 rejim</b>\n\n"
        "<i>Havolani yuboring va sinab ko'ring!</i>"
    )
    await message.answer(text, parse_mode="HTML")

