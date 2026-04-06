import asyncio
import logging
from celery_worker import celery_app
from core.gdrive_api import gdrive_api
from core.telegram_bot import send_telegram_notification
import time
import os

logger = logging.getLogger(__name__)


def run_async(coro):
    """Membantu menjalankan coroutine di konteks task synchronous Celery."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="tasks.run_rl_pipeline")
def run_rl_pipeline(self):
    """
    Menjalankan proses Gym/RL Environment.
    Dalam arsitektur terdesentralisasi, Worker Celery mengeksekusi step() untuk memicu rendering.
    """
    # Meng-import environment secara lazy di dalam fungsi untuk mencegah dependensi loading
    # besar (Gymnasium, MediaPipe, dll) langsung memori saat Celery boot-up

    logger.info("Starting Autonomous RL Pipeline Task...")
    try:
        from environment.clipper_env import ContentCreatorEnv

        env = ContentCreatorEnv()
        obs, info = env.reset()
        done = False

        while not done:
            # Sistem Policy akan mengatur action RL
            # Default action proxy: maju terus hingga render beres.
            action = 1
            obs, reward, done, truncated, info = env.step(action)
            if done or truncated:
                break

        logger.info("RL Pipeline Completed successfully.")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in RL pipeline task: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="tasks.distribute_and_notify")
def distribute_and_notify(
    self,
    video_path: str,
    meta_text_path: str,
    title: str,
    comment: str,
    tags: str,
    platform: str,
):
    """
    Task yang disebut di clipper_env.step() di kala status render telah usai.
    Bertugas memindahkan IO Heavy (upload gdrive) dan Notifikasi jaringan dari Main CPU Loop.
    """
    logger.info(
        f"Uploading asset to GDrive & Triggering Telegram Notification for: {platform}"
    )

    # Validasi path agar task digagalkan dari awal jika file tidak ada
    if not os.path.exists(video_path):
        logger.error(f"Video file {video_path} not found!")
        return {"status": "error", "message": "Video not found"}

    try:
        # 1. Jalankan Upload Async lewat thread wrapper
        upload_result = run_async(
            gdrive_api.upload_asset_async(video_path, meta_text_path, platform)
        )

        if not upload_result.get("success"):
            error_msg = upload_result.get("error", "Unknown error")
            logger.error(f"Drive Upload failed: {error_msg}")
            raise self.retry(
                countdown=300, max_retries=3
            )  # Retry unggahan setiap 5 menit jika gagal API

        v_link = upload_result.get("video_link")
        m_link = upload_result.get("meta_link", "N/A")

        # 2. Tentukan rekomendasi jadwal upload
        hour_now = time.localtime().tm_hour
        if 8 <= hour_now < 12:
            suggested_time = "Siang (12:00 - 13:00)"
        elif 12 <= hour_now < 18:
            suggested_time = "Sore (17:00 - 18:00)"
        else:
            suggested_time = "Malam (19:30 - 21:00)"

        # 3. Notifikasi Pengguna akhir agar tinggal copas
        run_async(
            send_telegram_notification(
                title=title,
                video_link=v_link,
                meta_link=m_link,
                comment=comment,
                suggested_time=suggested_time,
                platform=platform,
            )
        )

        logger.info(f"Successfully distributed to {platform}")
        return {
            "status": "uploaded_and_notified",
            "platform": platform,
            "video_link": v_link,
        }

    except Exception as e:
        logger.error(f"Distribution task encountered an error: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)
