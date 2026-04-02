from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import time
import random
from logger import logger
from environment.clipper_env import ContentCreatorEnv
from utils.dataset_prep import dataset_prep
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


def start_scheduler():
    """Menginisialisasi dan memulai APScheduler untuk orkestrasi waktu tayang UGC"""
    # Menggunakan zona waktu Indonesia (WIB)
    tz = pytz.timezone("Asia/Jakarta")
    scheduler = BackgroundScheduler(timezone=tz)

    # 07:30 - Trend News IG
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=7, minute=30),
        args=["Pagi Trend News (Eksplorasi Tinggi)", 0.6],
        id="pagi_trend",
    )

    # 12:15 - YT Insight
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=12, minute=15),
        args=["Siang YT Insight", 0.3],
        id="siang_insight",
    )

    # 19:00 - YT/IG Engagement (Prime Time)
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=19, minute=0),
        args=["Malam Prime Time (Eksploitasi)", 0.1],
        id="malam_prime",
    )

    # 22:00 - Edukasi
    scheduler.add_job(
        execute_scheduled_task,
        trigger=CronTrigger(hour=22, minute=0),
        args=["Malam Edukasi (Eksploitasi)", 0.1],
        id="malam_edu",
    )

    scheduler.start()
    logger.info(
        "📅 APScheduler berhasil diaktifkan. Menunggu jam tayang (07:30, 12:15, 19:00, 22:00 WIB)..."
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
