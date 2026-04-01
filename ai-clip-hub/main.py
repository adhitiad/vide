import multiprocessing
import time
import uvicorn
import random
from logger import logger
from environment.clipper_env import ContentCreatorEnv
from utils.dataset_prep import dataset_prep

def worker_process():
    """
    Loop Otonom Single Server (Server ALPHA).
    Mengeksekusi RL Environment menggunakan Epsilon-Greedy.
    """
    logger.info("🚀 Memulai Worker Process (Server ALPHA)...")

    # Inisialisasi Environment
    env = ContentCreatorEnv()

    # Epsilon (Peluang eksplorasi topik acak/baru)
    epsilon = 0.20 # 20% Eksplorasi Tren Baru, 80% Eksploitasi

    episode = 1

    # Cek & Persiapkan Dataset sebelum mulai
    logger.info("📦 Memeriksa Dataset Fine-Tuning...")
    dataset_prep.check_and_fallback()

    while True:
        try:
            state, info = env.reset()
            logger.info(f"--- 🎮 Memulai Episode {episode} ---")

            done = False
            step = 0

            # Loop dalam satu episode (10 langkah)
            while not done:
                logger.info(f"🔄 Menjalankan Step {step + 1} dari 10...")

                # Logic Epsilon-Greedy
                if random.random() < epsilon:
                    # 20%: Eksplorasi (Pilih aksi terakhir untuk RISET TREN BARU)
                    action = env.num_actions - 1
                    logger.info(f"🎲 [EKSPLORASI] Memulai riset tren viral baru... (Action: {action})")
                else:
                    # 80%: Eksploitasi (Pilih topik dengan skor tertinggi saat ini dari DB)
                    # np.argmax(state) mencari index nilai terbesar di array numpy
                    # Karena index terakhir (riset) skor fiktifnya 0.0,
                    # argmax akan memilih topik terbaik dari daftar.
                    best_action_idx = int(state[:-1].argmax()) if len(state) > 1 else 0
                    action = best_action_idx
                    logger.info(f"🎯 [EKSPLOITASI] Memilih aksi terbaik: Index {action} (Skor: {state[action]:.2f})")

                # Step env
                next_state, reward, done, truncated, step_info = env.step(action)

                # Update State
                state = next_state
                step += 1

                # Beri jeda/sleep 15-30 detik antar siklus (pembuatan video)
                sleep_time = random.uniform(15, 30)
                logger.info(f"⏳ Siklus selesai. Istirahat sejenak selama {sleep_time:.1f} detik...\n")
                time.sleep(sleep_time)

            episode += 1

        except Exception as e:
            logger.error(f"❌ Terjadi kesalahan fatal di Worker Process: {e}")
            logger.info("♻️ Mencoba restart Worker dalam 1 menit...")
            time.sleep(60)

def api_process():
    """Menjalankan server FastAPI menggunakan uvicorn"""
    logger.info("🌐 Memulai API Process & Dashboard...")
    # Matikan log default uvicorn agar tidak tercampur dengan log aplikasi kita
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False, log_config=None)

if __name__ == '__main__':
    logger.info("==========================================")
    logger.info("   🤖 AI-CLIP-HUB MULAI BERJALAN 🤖   ")
    logger.info("==========================================")

    p_worker = multiprocessing.Process(target=worker_process, name="WorkerProcess")
    p_api = multiprocessing.Process(target=api_process, name="APIProcess")

    p_worker.start()
    p_api.start()

    try:
        # Menjaga main thread tetap hidup dan menunggu proses selesai (yang mana loop abadi)
        p_worker.join()
        p_api.join()
    except KeyboardInterrupt:
        logger.info("🛑 Menerima sinyal penghentian (Ctrl+C). Mematikan sistem...")
        p_worker.terminate()
        p_api.terminate()
        p_worker.join()
        p_api.join()
        logger.info("✅ Sistem AI-Clip-Hub berhasil dimatikan dengan aman.")
