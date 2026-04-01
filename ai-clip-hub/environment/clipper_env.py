import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random
from logger import logger
from data.redis_client import redis_client
from core.downloader import downloader
from core.editor import video_editor
from core.knowledge import knowledge_base

class ContentCreatorEnv(gym.Env):
    """
    Custom Environment untuk Autonomous Content Creation.
    Agen memilih topik (Action), sistem menghasilkan video, dan menerima simulasi Views (Reward).
    """
    metadata = {'render_modes': ['console']}

    def __init__(self):
        super(ContentCreatorEnv, self).__init__()

        # 1. Action Space: Memilih salah satu dari N topik
        # Di awal, baca topik dari DB
        self.topics = self._get_active_topics()
        self.num_actions = len(self.topics)

        # Action space = index topik yang dipilih
        self.action_space = spaces.Discrete(self.num_actions)

        # 2. Observation Space: Skor saat ini dari semua topik
        # Shape: (num_actions, ) berisi skor float
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)

        # State saat ini (Skor topik)
        self.state = np.zeros(self.num_actions)
        self.current_step = 0

        logger.info(f"🌍 Environment ContentCreatorEnv diinisialisasi dengan {self.num_actions} topik aksi.")

    def _get_active_topics(self):
        # Ambil topik dari Redis/SQLite
        topics_data = redis_client.get_all_topics()
        if not topics_data:
             # Fallback jika kosong (seharusnya sudah ada default dari database.py)
             return ["bisnis online", "investasi pemula", "motivasi sukses", "teknologi terbaru", "AI tools 2024"]

        return [t["name"] for t in topics_data]

    def _update_state(self):
        # Perbarui observation state dari DB
        for i, topic in enumerate(self.topics):
            data = redis_client.get_topic_score(topic)
            self.state[i] = data.get("score", 0.0)
        return self.state

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.topics = self._get_active_topics()
        self.num_actions = len(self.topics)
        self.action_space = spaces.Discrete(self.num_actions)
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)

        state = self._update_state()
        return state, {}

    def step(self, action_idx):
        """
        Mengeksekusi aksi: Membuat video berdasarkan topik yang dipilih dan mengembalikan reward.
        """
        if action_idx >= len(self.topics):
            raise ValueError(f"Action index {action_idx} out of bounds")

        selected_topic = self.topics[action_idx]
        logger.info(f"🤖 [STEP {self.current_step}] Agen memilih topik: '{selected_topic}'")

        reward = 0.0
        done = False
        info = {"topic": selected_topic, "success": False, "views": 0}

        # 1. Pipeline Eksekusi Konten
        video_path = downloader.search_and_download(selected_topic)
        if video_path:
            # Edit Video
            edit_result = video_editor.process_video(video_path)
            if edit_result:
                # 2. Simulasi Reward (Views)
                # Dalam produksi nyata, ini bisa di-fetch dari YouTube Analytics API / TikTok API
                simulated_views = random.randint(100, 5000)

                # Bonus views jika pakai CTA tertentu atau durasi spesifik
                if "Komen" in edit_result.get("cta_used", ""):
                     simulated_views += int(simulated_views * 0.2) # +20% boost

                reward = float(simulated_views) / 100.0 # Normalisasi skor

                info["success"] = True
                info["views"] = simulated_views
                info["output_path"] = edit_result.get("output_path")

                logger.info(f"🏆 Simulasi Reward: {simulated_views} Views! (Skor: +{reward:.2f})")

                # Ekstrak Knowledge
                knowledge_base.extract_and_save(selected_topic, edit_result, reward)

            # Cleanup source video
            downloader.cleanup(video_path)
        else:
             # Penalti jika gagal mengunduh atau memproses
             reward = -1.0
             logger.warning(f"⚠️ Gagal memproses topik '{selected_topic}', Penalti -1.0")

        # 3. Update Skor Topik di Memory (Redis + SQLite)
        # Ambil state lama
        current_data = redis_client.get_topic_score(selected_topic)
        old_score = current_data.get("score", 0.0)
        times_chosen = current_data.get("times_chosen", 0) + 1

        # Exponential Moving Average (EMA) agar topik baru punya kesempatan naik
        alpha = 0.3 # Learning rate
        new_score = old_score + alpha * (reward - old_score)

        # Simpan ke DB
        redis_client.set_topic_score(selected_topic, new_score, times_chosen)
        logger.info(f"📈 Skor topik '{selected_topic}' diupdate: {old_score:.2f} -> {new_score:.2f} (Dipilih {times_chosen}x)")

        # Update Observation
        self.state = self._update_state()
        self.current_step += 1

        # Episodic (10 step = 1 episode)
        if self.current_step >= 10:
             done = True

        # Truncated is always False here, but required by gym step API signature
        truncated = False

        return self.state, reward, done, truncated, info

    def render(self):
        logger.info(f"State saat ini: {dict(zip(self.topics, self.state))}")
