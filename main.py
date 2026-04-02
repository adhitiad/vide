import multiprocessing
from dotenv import load_dotenv
import time
import uvicorn
import random
from logger import logger
from environment.clipper_env import ContentCreatorEnv
from utils.dataset_prep import dataset_prep
from scheduler_control import start_scheduler


load_dotenv()


def worker_process():
    """
    Loop Otonom (Server ALPHA).
    Sebagai tambahan dari APScheduler (jadwal), ini bisa berjalan konstan sebagai "Spam Bot"
    atau dimatikan jika hanya ingin mengandalkan Scheduler.
    Untuk sistem hybrid, kita biarkan worker ini berjalan lambat (sleep panjang)
    agar tidak over-upload ke YT/IG.
    """
    logger.info("🚀 Memulai Background Worker Process (Hybrid Mode)...")
    env = ContentCreatorEnv()
    epsilon = 0.20
    episode = 1

    logger.info("📦 Memeriksa Dataset Fine-Tuning...")
    dataset_prep.check_and_fallback()

    while True:
        try:
            state, info = env.reset()
            logger.info(f"--- 🎮 Memulai Episode Hybrid {episode} ---")

            done = False
            step = 0

            while not done:
                logger.info(f"🔄 Menjalankan Step {step + 1} dari 10...")
                if random.random() < epsilon:
                    action = env.num_actions - 1
                    logger.info(
                        f"🎲 [EKSPLORASI] Memulai riset tren viral Reddit (Aksi terakhir)..."
                    )
                else:
                    best_action_idx = int(state[:-1].argmax()) if len(state) > 1 else 0
                    action = best_action_idx
                    topic, visual = env._decode_action(action)
                    logger.info(
                        f"🎯 [EKSPLOITASI] Memilih aksi terbaik: {topic} (Visual Profil: {visual}) (Skor: {state[action]:.2f})"
                    )

                next_state, reward, done, truncated, step_info = env.step(action)
                state = next_state
                step += 1

                # Jeda 2-4 jam antar siklus agar akun YT/IG aman dari ban massal
                sleep_time = random.uniform(7200, 14400)
                logger.info(
                    f"⏳ Siklus selesai. Worker tidur selama {sleep_time/3600:.1f} jam...\n"
                )
                time.sleep(sleep_time)

            episode += 1

        except Exception as e:
            logger.error(f"❌ Kesalahan fatal di Worker Process: {e}")
            time.sleep(60)


def api_process():
    logger.info("🌐 Memulai Dashboard Web (God-Tier)...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False, log_config=None)


def scheduler_process():
    """Menjalankan jadwal APScheduler secara terpisah"""
    logger.info("📅 Memulai Jadwal Produksi Harian (07:30, 12:15, 19:00, 22:00)...")
    scheduler = start_scheduler()
    try:
        while True:
            time.sleep(60)
    except Exception as e:
        logger.error(f"Scheduler mati: {e}")


if __name__ == "__main__":
    logger.info("==============================================")
    logger.info("   🤖 AI-CLIP-HUB (GOD-TIER UGC EDITION) 🤖   ")
    logger.info("==============================================")

    p_worker = multiprocessing.Process(target=worker_process, name="WorkerProcess")
    p_api = multiprocessing.Process(target=api_process, name="APIProcess")
    p_scheduler = multiprocessing.Process(
        target=scheduler_process, name="SchedulerProcess"
    )

    p_worker.start()
    p_api.start()
    p_scheduler.start()

    try:
        p_worker.join()
        p_api.join()
        p_scheduler.join()
    except KeyboardInterrupt:
        logger.info("🛑 Mematikan sistem God-Tier...")
        p_worker.terminate()
        p_api.terminate()
        p_scheduler.terminate()
        logger.info("✅ Sistem AI-Clip-Hub mati dengan aman.")
