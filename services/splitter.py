import logging
import math
import subprocess
from pathlib import Path
from typing import List

from services.downloader import get_ffmpeg_binary

logger = logging.getLogger(__name__)


def split_video_by_size(
    video_path: Path,
    duration: float,
    max_part_size_mb: int = 47
) -> List[Path]:
    """
    Agar video hajmi 50 MB dan katta bo'lsa, uni ffmpeg yordamida
    qayta kodlamasdan (-c copy) belgilangan hajmga mos qismlarga bo'ladi.
    Sifat 100% saqlanadi va jarayon juda tez bajariladi.
    """
    file_size_bytes = video_path.stat().st_size
    max_part_bytes = max_part_size_mb * 1024 * 1024

    # Agar hajm limitdan kichik bo'lsa, bo'lish shart emas
    if file_size_bytes <= max_part_bytes:
        return [video_path]

    ffmpeg_bin = get_ffmpeg_binary()
    if not ffmpeg_bin:
        logger.error("ffmpeg topilmadi, videoni bo'lib bo'lmaydi.")
        return [video_path]

    # Qismlar sonini hisoblash
    num_parts = math.ceil(file_size_bytes / max_part_bytes)
    # Xavfsizlik uchun biroz kichikroq bo'laklarga ajratamiz
    part_duration = duration / num_parts

    logger.info(
        f"Video {file_size_bytes / (1024*1024):.1f} MB, {num_parts} ta qismga bo'linmoqda "
        f"(har bir qism ~{part_duration:.1f} soniya)..."
    )

    output_parts: List[Path] = []
    base_name = video_path.stem
    parent_dir = video_path.parent

    for i in range(num_parts):
        start_time = i * part_duration
        part_file = parent_dir / f"{base_name}_part{i+1}.mp4"

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(part_duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(part_file)
        ]

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            if part_file.exists() and part_file.stat().st_size > 0:
                output_parts.append(part_file)
            else:
                logger.warning(f"{part_file} yaratilmadi yoki bo'sh!")
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg bo'lishda xatolik: {e.stderr.decode('utf-8', errors='ignore')}")

    # Agar muvaffaqiyatli bo'lingan bo'lsa, ularni qaytaramiz
    if output_parts:
        return output_parts

    # Agar bo'lish o'xshamasa, asl faylni qaytaramiz
    return [video_path]
