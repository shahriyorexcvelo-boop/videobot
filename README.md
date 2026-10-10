# 🎬 VIDEO FAST — Instagram & YouTube Telegram Bot (2 GB & 24/7 Render.com)

Python, **aiogram 3**, **Telethon (MTProto)** va **yt-dlp** asosida yaratilgan professional video yuklovchi Telegram bot.

---

## 🌟 Asosiy Imkoniyatlar

- **🎯 Sifat Tanlash**: `360p`, `480p`, `720p (HD)` va `1080p (Full HD)` tugmalari orqali aniq sifatni tanlash.
- **🚀 2 GB gacha Yaxlit Video**: MTProto (Telethon) integratsiyasi orqali videolarni **qismlarga bo‘lmasdan**, to‘liq bitta video qilib jo‘natadi!
- **⚡️ 0.2 Soniyali Kesh**: Bir marta yuklangan videolar keyingi safar oniy (instant) tezlikda yetkaziladi.
- **⏱ Jonli ETA & Progress-Bar**: Qancha vaqt qolgani, foiz va yuklash tezligi jonli yangilanadi.
- **🌐 Render.com 24/7 Qo‘llab-quvvatlash**: Ichki web-server tufayli Render.com da bepul 24/7 uzluksiz ishlaydi.

---

## 🚀 Render.com da 24/7 Ishga Tushirish Yo‘riqnomasi

### 1-qadam: GitHub ga yuklash
Loyihangizni GitHub profilingizga yuklang (repo yaratib, push qiling).

### 2-qadam: Render.com da loyiha ochish
1. [dashboard.render.com](https://dashboard.render.com) ga kiring.
2. **New +** -> **Web Service** ni tanlang.
3. GitHub reponi ulang (`video.bot`).
4. Sozlamalar:
   - **Name**: `video-telegram-bot`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Plan**: `Free` (Bepul)

### 3-qadam: Environment Variables (Muhit O‘zgaruvchilari)
Render sozlamalarida **Environment Variables** bo‘limiga `.env` dagi ma'lumotlarni kiriting:
- `BOT_TOKEN`: `sizning_bot_tokeningiz` (BotFather'dan olingan)
- `API_ID`: `sizning_api_id` (my.telegram.org'dan olingan)
- `API_HASH`: `sizning_api_hash`
- `PORT`: `8080`
- `DOWNLOAD_DIR`: `downloads`

So‘ng **Deploy Web Service** tugmasini bosing!

### 4-qadam: 24/7 Uxlab qolmasligi uchun (UptimeRobot)
Render bepul xizmati 15 daqiqada uxlab qolmasligi uchun:
1. [uptimerobot.com](https://uptimerobot.com) saytiga bepul ro‘yxatdan o‘ting.
2. **Add New Monitor** tugmasini bosing.
3. Monitor Type: `HTTP(s)`
4. URL: Render bergan linkni qo‘ying (masalan: `https://video-telegram-bot.onrender.com/health`).
5. Interval: `5 minutes`.
Natijada botingiz bir umr 24/7 uxlamasdan ishlaydi!

---

## 💻 Mahalliy (Lokal) Ishga Tushirish

```bash
cd /Users/shahriyoreshimbetov/video.bot
./venv/bin/python bot.py
```
