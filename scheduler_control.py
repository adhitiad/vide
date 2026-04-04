from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import time
import random
from logger import logger
from environment.clipper_env import ContentCreatorEnv
from utils.dataset_prep import dataset_prep
from core.analytics_tracker import run_all_trackers
import pytz


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


def retry_failed_uploads():
    """
    Coba ulang video yang gagal di-upload kemarin (status 'failed' di DB).
    Dipanggil setiap hari jam 14:30 WIB (setelah kuota API YouTube di-reset).
    """
    from data.database import SessionLocal
    from data.models import UploadQueue
    from core.uploader_yt import youtube_uploader
    import datetime

    logger.info("🔄 [RETRY JOB] Mengecek video yang gagal untuk di-retry...")
    session = SessionLocal()
    try:
        # Ambil video yang statusnya 'failed' dari hari sebelumnya
        failed_videos = (
            session.query(UploadQueue)
            .filter(UploadQueue.status == "failed")
            .order_by(UploadQueue.created_at.asc())
            .limit(3)  # Maksimal 3 retry sekaligus agar tidak membanjiri kuota baru
            .all()
        )

        if not failed_videos:
            logger.info("✅ [RETRY JOB] Tidak ada video gagal. Kuota bersih!")
            return

        logger.info(
            f"⚠️ [RETRY JOB] Ditemukan {len(failed_videos)} video gagal. Mencoba kembali..."
        )

        for video in failed_videos:
            logger.info(
                f"📤 [RETRY] Mencoba upload ulang: '{video.title}' ({video.video_path})"
            )
            video.status = "retrying"
            session.commit()

            yt_url = youtube_uploader.upload_to_youtube_shorts(
                video_path=video.video_path,
                title=video.title,
                description=video.description,
                tags=video.tags.split(",") if video.tags else [],
            )

            if yt_url:
                video.status = "published"
                video.published_url = yt_url
                video.published_at = datetime.datetime.utcnow()
                logger.info(f"🎉 [RETRY] Berhasil! {yt_url}")
            else:
                video.status = "failed"
                video.retry_count = (video.retry_count or 0) + 1
                logger.error(
                    f"❌ [RETRY] Masih gagal setelah retry ke-{video.retry_count}."
                )

            session.commit()

    except Exception as e:
        logger.error(f"❌ [RETRY JOB] Error saat retry: {e}")
        session.rollback()
    finally:
        session.close()


def start_scheduler():
    """
    Inisialisasi APScheduler dengan strategi 'Prime Time Upload'.

    STRATEGI MINGGU 1-2 (Anti-Spam Algorithm):
    - AI memproduksi video secara internal (queue mode) setiap 4 jam sekali.
    - Upload ke YouTube HANYA 2x sehari di prime time: Jam 12:00 & 19:00 WIB.
    - Konsistensi > Kuantitas Brutal. Algoritma YouTube menghargai ritme yang stabil.
    - Retry video gagal setiap jam 14:30 WIB (setelah kuota API di-reset tengah malam Pasifik).
    """
    # Menggunakan zona waktu Indonesia (WIB)
    tz = pytz.timezone("Asia/Jakarta")
    scheduler = BackgroundScheduler(timezone=tz)

    # =========================================================
    # JOB 1: Produksi Video (Setiap 4 Jam) - TETAP BERJALAN
    # AI mengedit video dan menyimpan ke antrian lokal,
    # TAPI TIDAK langsung upload. Upload dilakukan oleh Job 2.
    # =========================================================
    scheduler.add_job(
        execute_scheduled_task,
        trigger=IntervalTrigger(hours=4),
        args=["Siklus Produksi 4-Jam (Hybrid RL)", 0.2],
        id="produksi_empat_jam",
        replace_existing=True,
    )

    # =========================================================
    # JOB 2: Upload Prime Time SIANG - Jam 12:00 WIB
    # Maksimal 1 video yang paling kuat diunggah saat makan siang.
    # =========================================================
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=12, minute=0, timezone=tz),
        args=["Upload Prime Time Siang (12:00 WIB)", 0.1],  # Epsilon rendah = Eksploitasi
        id="upload_prime_siang",
        replace_existing=True,
    )

    # =========================================================
    # JOB 3: Upload Prime Time MALAM - Jam 19:00 WIB
    # Slot prime time terkuat. Penonton aktif setelah pulang kerja/sekolah.
    # =========================================================
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=19, minute=0, timezone=tz),
        args=["Upload Prime Time Malam (19:00 WIB)", 0.1],  # Epsilon rendah = Eksploitasi
        id="upload_prime_malam",
        replace_existing=True,
    )

    # =========================================================
    # JOB 4: Retry Video Gagal - Jam 14:30 WIB
    # YouTube API quota reset tengah malam waktu Pasifik (~14:00-15:00 WIB).
    # Kita tunggu 30 menit ekstra agar reset pasti selesai.
    # =========================================================
    scheduler.add_job(
        retry_failed_uploads,
        trigger=CronTrigger(hour=14, minute=30, timezone=tz),
        id="retry_failed_uploads",
        replace_existing=True,
    )

    # =========================================================
    # JOB 5: Auto-Analytics Tracker - Jam 23:30 WIB
    # Tarik stats (views/likes/comments) dari YouTube & Instagram API.
    # Update performance_status di DB:
    #   - GOOD      → views >= 100 setelah 24 jam
    #   - LOW_VIEWS → views < 100 setelah 24 jam (memicu Self-Correction besok)
    #   - VIRAL     → views >= 1000 (topik mendapat bonus score di Redis)
    # =========================================================
    scheduler.add_job(
        run_all_trackers,
        trigger=CronTrigger(hour=23, minute=30, timezone=tz),
        id="auto_analytics_tracker",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "📅 APScheduler berhasil diaktifkan.\n"
        "   🎬 Produksi      : Setiap 4 jam (AI terus produksi, simpan ke queue)\n"
        "   📤 Upload        : Prime Time Siang 12:00 WIB & Malam 19:00 WIB (2 video/hari)\n"
        "   🔄 Retry Gagal   : Setiap hari jam 14:30 WIB (setelah quota API reset)\n"
        "   📊 Analytics     : Setiap hari jam 23:30 WIB (update views/likes + evaluasi status)\n"
        "   🔥 Self-Correct  : Aktif otomatis jika ditemukan video LOW_VIEWS saat step() berikutnya\n"
        "   ✅ Strategi      : Konsistensi > Kuantitas - Anti Spam Algorithm"
    )
    return scheduler


if __name__ == "__main__":
    start_scheduler()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler dimatikan")
        pass
