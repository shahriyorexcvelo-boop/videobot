"""
Render <-> Lokal "handoff" (navbat almashish) mexanizmi.

Telegram bitta bot tokeni bilan faqat BITTA joyda getUpdates (polling) qilishga ruxsat beradi.
Shuning uchun:
  - Render doim ishlaydi va polling qiladi.
  - Lokal bot ishga tushganda Render'ga "lease" (ijara) so'rovini yuboradi va har 15 soniyada yangilab turadi.
  - Lease faol bo'lsa, Render polling'ni to'xtatadi (web server ishlashda davom etadi).
  - Lokal bot yopilsa (release) yoki signal LEASE_TTL soniya kelmasa, Render polling'ni qayta yoqadi.
"""
import asyncio
import hmac
import logging
import time
from typing import Optional

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher

from config import HANDOFF_SECRET, RENDER_URL

logger = logging.getLogger(__name__)

LEASE_TTL = 45          # soniya: shu vaqt ichida heartbeat kelmasa, Render qayta ishga tushadi
HEARTBEAT_INTERVAL = 15  # soniya: lokal bot qanchalik tez-tez signal yuboradi


# ─────────────────────────── Render tomoni ───────────────────────────

class RenderPollingSupervisor:
    """Render'da polling'ni lokal lease holatiga qarab yoqib/o'chirib turadi."""

    def __init__(self, dp: Dispatcher, bot: Bot):
        self.dp = dp
        self.bot = bot
        self.lease_until: float = 0.0
        self._polling_task: Optional[asyncio.Task] = None
        self._wake = asyncio.Event()

    @property
    def local_active(self) -> bool:
        return time.time() < self.lease_until

    @property
    def polling(self) -> bool:
        return self._polling_task is not None and not self._polling_task.done()

    def _check_secret(self, request: web.Request) -> bool:
        provided = request.headers.get("X-Handoff-Secret", "")
        return bool(HANDOFF_SECRET) and hmac.compare_digest(provided, HANDOFF_SECRET)

    async def handle_lease(self, request: web.Request) -> web.Response:
        if not self._check_secret(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            data = await request.json()
        except Exception:
            data = {}
        action = data.get("action", "acquire")

        if action == "release":
            self.lease_until = 0.0
            logger.info("🔁 Lokal bot lease'ni bo'shatdi. Render polling'ni qayta yoqadi.")
        else:
            was_active = self.local_active
            self.lease_until = time.time() + LEASE_TTL
            if not was_active:
                logger.info("🔁 Lokal bot ulandi. Render polling'ni to'xtatmoqda...")

        self._wake.set()
        # Supervisor holatni o'zgartirishiga qisqa vaqt beramiz
        await asyncio.sleep(0.5)
        return web.json_response({"local_active": self.local_active, "render_polling": self.polling})

    def register_routes(self, app: web.Application):
        app.router.add_post("/lease", self.handle_lease)

    async def _start_polling(self):
        logger.info("▶️ Render polling yoqildi.")
        self._polling_task = asyncio.create_task(
            self.dp.start_polling(self.bot, handle_signals=False, close_bot_session=False)
        )

    async def _stop_polling(self):
        logger.info("⏸ Render polling to'xtatildi (lokal bot ishlayapti).")
        try:
            await self.dp.stop_polling()
        except RuntimeError:
            pass
        if self._polling_task:
            try:
                await self._polling_task
            except Exception as e:
                logger.warning(f"Polling to'xtatishda ogohlantirish: {e}")
        self._polling_task = None

    async def run(self):
        while True:
            if self.local_active and self.polling:
                await self._stop_polling()
            elif not self.local_active and not self.polling:
                await self._start_polling()

            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


# ─────────────────────────── Lokal tomoni ───────────────────────────

async def _send_lease(session: aiohttp.ClientSession, action: str) -> Optional[dict]:
    url = f"{RENDER_URL.rstrip('/')}/lease"
    try:
        async with session.post(
            url,
            json={"action": action},
            headers={"X-Handoff-Secret": HANDOFF_SECRET},
            timeout=aiohttp.ClientTimeout(total=60),  # Render bepul tarifda uyg'onishi uchun
        ) as resp:
            if resp.status == 401:
                logger.error("❌ HANDOFF_SECRET Render'dagi qiymat bilan mos emas!")
                return None
            return await resp.json()
    except Exception as e:
        logger.warning(f"Render bilan bog'lanib bo'lmadi ({action}): {e}")
        return None


async def acquire_from_render(session: aiohttp.ClientSession) -> None:
    """Lokal bot ishga tushishidan oldin Render'ni to'xtatib turadi."""
    logger.info(f"🔁 Render'ga ({RENDER_URL}) to'xtash so'rovi yuborilmoqda...")
    for _ in range(10):
        res = await _send_lease(session, "acquire")
        if res and not res.get("render_polling"):
            logger.info("✅ Render polling'ni to'xtatdi. Lokal bot ishga tushmoqda.")
            # Render'ning ochiq qolgan getUpdates so'rovi yopilishi uchun qisqa kutish
            await asyncio.sleep(2)
            return
        await asyncio.sleep(1.5)
    logger.warning("⚠️ Render javobini tasdiqlab bo'lmadi. Baribir ishga tushirilmoqda (qisqa konflikt bo'lishi mumkin).")


async def heartbeat_loop(session: aiohttp.ClientSession) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        await _send_lease(session, "acquire")


async def release_to_render(session: aiohttp.ClientSession) -> None:
    res = await _send_lease(session, "release")
    if res is not None:
        logger.info("🔁 Render'ga boshqaruv qaytarildi.")
