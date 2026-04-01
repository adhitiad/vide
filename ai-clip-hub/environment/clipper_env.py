import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random
from logger import logger
from data.redis_client import redis_client
from core.downloader import downloader
from core.editor import video_editor
from core.knowledge import knowledge_base
from core.researcher import get_trending_topic

class ContentCreatorEnv(gym.Env):
    """
    Custom Environment untuk Autonomous Content Creation.
    Agen memilih topik (Action), sistem menghasilkan video, dan menerima simulasi Views (Reward).
    Aksi khusus (Eksplorasi) akan memicu pencarian topik viral baru.
    """
    metadata = {'render_modes': ['console']}

    def __init__(self):
        super(ContentCreatorEnv, self).__init__()

        # 1. Action Space
        self.topics = self._get_active_topics()

        # Action space = index topik yang dipilih,
        # +1 untuk aksi "EKSPLORASI / RISET TREN BARU"
        self.num_actions = len(self.topics) + 1
        self.action_space = spaces.Discrete(self.num_actions)

        # 2. Observation Space: Skor saat ini dari semua topik, ditambah 1 slot untuk "Riset Baru"
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)

        # State saat ini (Skor topik)
        self.state = np.zeros(self.num_actions)
        self.current_step = 0

        logger.info(f"🌍 Environment ContentCreatorEnv diinisialisasi dengan {self.num_actions-1} topik + 1 aksi riset.")

    def _get_active_topics(self):
        topics_data = redis_client.get_all_topics()
        if not topics_data:
             return []
        return [t["name"] for t in topics_data]

    def _update_state(self):
        # Perbarui observation state dari DB
        self.state = np.zeros(self.num_actions)
        for i, topic in enumerate(self.topics):
            data = redis_client.get_topic_score(topic)
            self.state[i] = data.get("score", 0.0)

        # Skor fiktif untuk slot eksplorasi (index terakhir)
        self.state[-1] = 0.0

        return self.state

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0

        # Update ruang aksi setiap kali episode reset
        self.topics = self._get_active_topics()
        self.num_actions = len(self.topics) + 1
        self.action_space = spaces.Discrete(self.num_actions)
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)

        state = self._update_state()
        return state, {}

    def step(self, action_idx):
        """
        Mengeksekusi aksi: Membuat video berdasarkan topik yang dipilih dan mengembalikan reward.
        Jika aksi adalah index terakhir, lakukan riset tren baru.
        """
        if action_idx >= self.num_actions:
            raise ValueError(f"Action index {action_idx} out of bounds")

        # Cek apakah ini aksi riset (eksplorasi)
        is_explore_action = (action_idx == self.num_actions - 1)
        is_new_topic = False

        if is_explore_action:
            # Mode Eksplorasi: Cari topik viral
            selected_topic = get_trending_topic()

            # Cek apakah topik sudah ada di database (case-insensitive)
            existing_topics_lower = [t.lower() for t in self.topics]
            if selected_topic.lower() not in existing_topics_lower:
                logger.info(f"✨ Menambahkan topik viral baru ke memori: '{selected_topic}'")
                is_new_topic = True

                # Kita TIDAK perlu menyimpan awal ke DB di sini karena akan di-set di akhir step.
                # Kita hanya perlu update state internal environment.
                self.topics.append(selected_topic)

                # Perbarui panjang action/observation space SECARA DINAMIS
                self.num_actions = len(self.topics) + 1
                self.action_space = spaces.Discrete(self.num_actions)
                self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)

            else:
                logger.info(f"ℹ️ Topik viral '{selected_topic}' sudah ada di database. Mengeksekusinya.")
        else:
            # Mode Eksploitasi: Ambil topik dari daftar
            selected_topic = self.topics[action_idx]

        logger.info(f"🤖 [STEP {self.current_step}] Agen memproses topik: '{selected_topic}'")

        reward = 0.0
        done = False
        info = {"topic": selected_topic, "success": False, "views": 0, "is_exploration": is_explore_action}

        # 1. Pipeline Eksekusi Konten
        video_path = downloader.search_and_download(selected_topic)
        if video_path:
            # Edit Video
            edit_result = video_editor.process_video(video_path)
            if edit_result:
                # 2. Simulasi Reward (Views)
                simulated_views = random.randint(100, 5000)

                # Bonus views jika pakai CTA tertentu
                if "Komen" in edit_result.get("cta_used", ""):
                     simulated_views += int(simulated_views * 0.2)

                reward = float(simulated_views) / 100.0

                info["success"] = True
                info["views"] = simulated_views
                info["output_path"] = edit_result.get("output_path")

                logger.info(f"🏆 Simulasi Reward: {simulated_views} Views! (Skor: +{reward:.2f})")

                # Ekstrak Knowledge
                knowledge_base.extract_and_save(selected_topic, edit_result, reward)

            # Cleanup source video
            downloader.cleanup(video_path)
        else:
             reward = -1.0
             logger.warning(f"⚠️ Gagal memproses topik '{selected_topic}', Penalti -1.0")

        # 3. Update Skor Topik di Memory (Redis + SQLite)
        if is_new_topic:
            # Topik benar-benar baru, beri skor basis (baseline) yang tinggi agar dicoba lagi
            old_score = 15.0
            times_chosen = 1
        else:
            current_data = redis_client.get_topic_score(selected_topic)
            old_score = current_data.get("score", 0.0)
            times_chosen = current_data.get("times_chosen", 0) + 1

        # EMA (Exponential Moving Average)
        alpha = 0.3
        new_score = old_score + alpha * (reward - old_score)

        redis_client.set_topic_score(selected_topic, new_score, times_chosen)
        logger.info(f"📈 Skor topik '{selected_topic}' diupdate: {old_score:.2f} -> {new_score:.2f} (Dipilih {times_chosen}x)")

        # Update Observation
        self.state = self._update_state()
        self.current_step += 1

        if self.current_step >= 10:
             done = True

        return self.state, reward, done, False, info

    def render(self):
        # Hanya tampilkan yang eksis di topics
        logger.info(f"State saat ini: {dict(zip(self.topics, self.state[:-1]))}")
