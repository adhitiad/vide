from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import time
import random
import datetime
import pytz
from logger import logger
from environment.clipper_env import ContentCreatorEnv
from utils.dataset_prep import dataset_prep
from data.mongodb_client import db
from data.models import UploadQueue, PublishedVideo
from core.uploader_manager import uploader_manager
from core.analytics_tracker import run_all_trackers

def execute_scheduled_task(job_name: str, epsilon: float = 0.2):
    """Fungsi pembungkus untuk menjalankan agen RL di waktu tertentu"""
    logger.info(f"⏰ [JADWAL APSCHEDULER] Menjalankan {job_name}...")

    env = ContentCreatorEnv()
    state, info = env.reset()

    # Pilih aksi Epsilon-Greedy
    if random.random() < epsilon:
        action = env.num_actions - 1
        logger.info(f"🎲 [APSCHEDULER Eksplorasi] Memulai riset tren viral Reddit...")
    else:
        # Cari aksi terbaik (Kombinasi Topik + Visual Profile terbaik)
        best_action_idx = int(state[:-1].argmax()) if len(state) > 1 else 0
        action = best_action_idx
        topic, visual = env._decode_action(action)
        logger.info(
            f"🎯 [APSCHEDULER Eksploitasi] Memilih aksi terbaik: {topic} (Visual: {visual})"
        )

    next_state, reward, done, truncated, step_info = env.step(action)
    logger.info(f"✅ Jadwal {job_name} Selesai. (Reward: {reward:.2f})")


def process_upload_queue():
    """
    Worker yang mengecek antrean upload secara berkala.
    Mendukung strategi 'Staggered Upload' (berjeda) antar platform.
    """
    logger.info("📡 [QUEUE WORKER] Mengecek antrean upload terjadwal...")
    try:
        now = datetime.datetime.utcnow()
        # Ambil tugas yang sudah tiba waktunya (MongoDB query)
        pending_tasks_data = db.upload_queue.find({
            "status": "pending",
            "scheduled_at": {"$lte": now}
        }).sort("scheduled_at", 1)

        pending_tasks = [UploadQueue.from_dict(t) for t in pending_tasks_data]

        if not pending_tasks:
            return

        logger.info(f"📋 [QUEUE WORKER] Ditemukan {len(pending_tasks)} tugas siap eksekusi.")

        for task in pending_tasks:
            platform = str(task.platform).lower()
            logger.info(f"📤 [QUEUE] Memproses {platform} untuk: {task.title}")
            
            # Update status di MongoDB
            db.upload_queue.update_one({"_id": task._id}, {"$set": {"status": "uploading"}})

            success_url = None
            platform_video_id = None

            try:
                # Menggunakan casting str() untuk menghindari peringatan Pyright
                v_path = str(task.video_path)
                v_title = str(task.title)
                v_desc = str(task.description)
                v_tags = str(task.tags).split(",") if task.tags else []

                # Gunakan UploaderManager (Unified Interface)
                success_url = uploader_manager.upload_video(
                    platform=platform,
                    video_path=v_path,
                    title=v_title,
                    description=v_desc
                )

                if success_url:
                    # Ekstrak ID video jika memungkinkan (utamanya untuk YouTube/Instagram)
                    if platform == "youtube" and "/shorts/" in success_url:
                         platform_video_id = success_url.split("/shorts/")[-1].split("?")[0].strip()
                    elif platform == "instagram" and "/reels/" in success_url:
                         platform_video_id = success_url.split("/reels/")[-1].strip("/")

                if success_url:
                    # Update sukses di MongoDB
                    db.upload_queue.update_one({"_id": task._id}, {
                        "$set": {
                            "status": "published",
                            "published_url": success_url,
                            "published_at": datetime.datetime.utcnow()
                        }
                    })
                    
                    # Simpan ke track record analytics MongoDB
                    new_pub = PublishedVideo(
                        topic_name=task.topic_name,
                        platform=platform,
                        video_url=success_url,
                        platform_video_id=platform_video_id,
                        performance_status="PENDING"
                    )
                    db.published_videos.insert_one(new_pub.to_dict())
                    logger.info(f"🎉 [QUEUE] {platform} BERHASIL dipublish!")
                else:
                    db.upload_queue.update_one({"_id": task._id}, {
                        "$set": {
                            "status": "failed",
                            "last_error": "Uploader returned None/False"
                        }
                    })
                    logger.error(f"❌ [QUEUE] {platform} GAGAL.")

            except Exception as inner_e:
                db.upload_queue.update_one({"_id": task._id}, {
                    "$set": {
                        "status": "failed",
                        "last_error": str(inner_e)
                    }
                })
                logger.error(f"❌ [QUEUE] Fatal error pada {platform}: {inner_e}")

    except Exception as e:
        logger.error(f"❌ [QUEUE WORKER] Error sistem: {e}")


def retry_failed_uploads():
    """
    Coba ulang video yang gagal di-upload (status 'failed' di DB).
    Biasanya dipanggil setelah kuota API reset.
    """
    logger.info("🔄 [RETRY JOB] Mengecek video yang gagal untuk di-retry...")
    try:
        failed_tasks_data = db.upload_queue.find({
            "status": "failed",
            "retry_count": {"$lt": 3}  # Hardcoded max_retries atau ambil dari model
        }).sort("created_at", 1).limit(5)

        failed_tasks = [UploadQueue.from_dict(t) for t in failed_tasks_data]

        if not failed_tasks:
            logger.info("✅ [RETRY JOB] Tidak ada video gagal yang perlu di-retry.")
            return

        for task in failed_tasks:
            logger.info(f"📤 [RETRY] Mengembalikan status {task.platform} ke 'pending' untuk diproses ulang.")
            
            db.upload_queue.update_one({"_id": task._id}, {
                "$set": {
                    "status": "pending",
                    "retry_count": (task.retry_count or 0) + 1,
                    "scheduled_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
                }
            })
            
    except Exception as e:
        logger.error(f"❌ [RETRY JOB] Error: {e}")


def start_scheduler():
    """
    Inisialisasi APScheduler dengan strategi 'Prime Time Upload'.
    """
    tz = pytz.timezone("Asia/Jakarta")
    scheduler = BackgroundScheduler(timezone=tz)

    # Produksi Video (Setiap 4 Jam)
    scheduler.add_job(
        execute_scheduled_task,
        trigger=IntervalTrigger(hours=4),
        args=["Siklus Produksi 4-Jam (Hybrid RL)", 0.2],
        id="produksi_empat_jam",
        replace_existing=True,
    )

    # Upload Prime Time Siang
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=12, minute=0, timezone=tz),
        args=["Upload Prime Time Siang (12:00 WIB)", 0.1],
        id="upload_prime_siang",
        replace_existing=True,
    )

    # Upload Prime Time Malam
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=19, minute=0, timezone=tz),
        args=["Upload Prime Time Malam (19:00 WIB)", 0.1],
        id="upload_prime_malam",
        replace_existing=True,
    )

    # Retry Video Gagal (Setiap hari jam 14:30 WIB)
    scheduler.add_job(
        retry_failed_uploads,
        trigger=CronTrigger(hour=14, minute=30, timezone=tz),
        id="retry_failed_uploads",
        replace_existing=True,
    )

    # Auto-Analytics Tracker (Setiap hari jam 23:30 WIB)
    scheduler.add_job(
        run_all_trackers,
        trigger=CronTrigger(hour=23, minute=30, timezone=tz),
        id="auto_analytics_tracker",
        replace_existing=True,
    )

    # Queue Worker (Setiap 10 Menit)
    scheduler.add_job(
        process_upload_queue,
        trigger=IntervalTrigger(minutes=10),
        id="process_upload_queue",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("📅 APScheduler berhasil diaktifkan dengan Queue System (YT, IG, FB, TT).")
    return scheduler


if __name__ == "__main__":
    start_scheduler()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler dimatikan")
        pass
