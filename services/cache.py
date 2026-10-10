import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from config import BASE_DIR

DB_PATH = BASE_DIR / "cache.db"


class MediaCache:
    """
    Telegram file_id'larini saqlash uchun SQLite asosidagi tezkor kesh.
    Bir marta yuborilgan videoni keyingi safar yuklab o'tirmasdan,
    0.5 soniyada Telegram serverining o'zidan jo'natish imkonini beradi.
    """
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS video_cache (
                    url_key TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    title TEXT,
                    duration INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get(self, url_key: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_id, title, duration FROM video_cache WHERE url_key = ?",
                (url_key,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "file_id": row[0],
                    "title": row[1],
                    "duration": row[2]
                }
        return None

    def set(self, url_key: str, file_id: str, title: str, duration: Optional[int] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO video_cache (url_key, file_id, title, duration)
                VALUES (?, ?, ?, ?)
            """, (url_key, file_id, title, duration))
            conn.commit()


# Global kesh obyekti
media_cache = MediaCache()
