import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random
from logger import logger
from data.redis_client import redis_client
from data.database import SessionLocal
from data.models import PublishedVideo, TopicMemory
from core.downloader import downloader
from core.editor import video_editor
from core.knowledge import knowledge_base
from core.researcher import get_trending_topic
from core.uploader import youtube_uploader

class ContentCreatorEnv(gym.Env):
    """
    Custom Environment untuk Autonomous Content Creation & Auto-Upload.
    Agen memilih topik, menghasilkan video Shorts, mengunggahnya secara nyata,
    dan menerima Reward berdasarkan keberhasilan publikasi internet.
    """
    metadata = {'render_modes': ['console']}

    def __init__(self):
        super(ContentCreatorEnv, self).__init__()

        self.topics = self._get_active_topics()
        self.num_actions = len(self.topics) + 1
        self.action_space = spaces.Discrete(self.num_actions)
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)

        self.state = np.zeros(self.num_actions)
        self.current_step = 0

        logger.info(f"🌍 Environment ContentCreatorEnv (Auto-Upload) diinisialisasi dengan {self.num_actions-1} topik + 1 aksi riset.")

    def _get_active_topics(self):
        topics_data = redis_client.get_all_topics()
        if not topics_data:
             return []
        return [t["name"] for t in topics_data]

    def _update_state(self):
        self.state = np.zeros(self.num_actions)
        for i, topic in enumerate(self.topics):
            data = redis_client.get_topic_score(topic)
            self.state[i] = data.get("score", 0.0)
        self.state[-1] = 0.0
        return self.state

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0

        self.topics = self._get_active_topics()
        self.num_actions = len(self.topics) + 1
        self.action_space = spaces.Discrete(self.num_actions)
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)

        state = self._update_state()
        return state, {}

    def _save_published_video(self, topic_name: str, video_url: str):
        """Menyimpan data video yang berhasil diunggah ke SQLite"""
        session = SessionLocal()
        try:
            new_video = PublishedVideo(
                topic_name=topic_name,
                video_url=video_url,
                views=0
            )
            session.add(new_video)
            session.commit()
            logger.info(f"💾 Disimpan ke DB PublishedVideo: {video_url} untuk topik '{topic_name}'")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Gagal menyimpan PublishedVideo ke DB: {e}")
        finally:
            session.close()

    def step(self, action_idx):
        if action_idx >= self.num_actions:
            raise ValueError(f"Action index {action_idx} out of bounds")

        is_explore_action = (action_idx == self.num_actions - 1)
        is_new_topic = False

        if is_explore_action:
            selected_topic = get_trending_topic()
            existing_topics_lower = [t.lower() for t in self.topics]
            if selected_topic.lower() not in existing_topics_lower:
                logger.info(f"✨ Menambahkan topik viral baru ke memori: '{selected_topic}'")
                is_new_topic = True
                self.topics.append(selected_topic)
                self.num_actions = len(self.topics) + 1
                self.action_space = spaces.Discrete(self.num_actions)
                self.observation_space = spaces.Box(low=0, high=np.inf, shape=(self.num_actions,), dtype=np.float32)
            else:
                logger.info(f"ℹ️ Topik viral '{selected_topic}' sudah ada di database. Mengeksekusinya.")
        else:
            selected_topic = self.topics[action_idx]

        logger.info(f"🤖 [STEP {self.current_step}] Agen memproses topik: '{selected_topic}'")

        # Default penalti jika proses terputus
        reward = -2.0
        done = False
        info = {"topic": selected_topic, "success": False, "url": None}

        # Pipeline Eksekusi Konten
        video_path = downloader.search_and_download(selected_topic)
        if video_path:
            # Edit Video
            edit_result = video_editor.process_video(video_path)
            if edit_result:
                # Transkrip/caption dari video digunakan sebagai deskripsi dan training data
                description = edit_result.get("transcript", "Video singkat tentang " + selected_topic)
                output_video_path = edit_result.get("output_path")

                # Ekstrak Knowledge untuk fine-tuning LLM sebelum upload
                knowledge_base.extract_and_save(selected_topic, edit_result, reward=1.0)

                # UPLOAD KE YOUTUBE SHORTS
                title = f"{selected_topic.capitalize()} | Fakta Menarik #Shorts"
                tags = ["Shorts", selected_topic.replace(" ", ""), "Viral", "Trending", "Indonesia"]

                # default privacy_status = "public"
                upload_url = youtube_uploader.upload_to_youtube_shorts(
                    video_path=output_video_path,
                    title=title,
                    description=description,
                    tags=tags,
                    privacy_status="public"
                )

                if upload_url:
                    # Upload Berhasil! Beri Reward positif
                    reward = 1.0
                    info["success"] = True
                    info["url"] = upload_url
                    logger.info(f"🏆 REWARD +1.0! Publikasi internet berhasil untuk topik '{selected_topic}'")

                    # Simpan ke tabel PublishedVideo
                    self._save_published_video(selected_topic, upload_url)
                else:
                    # Gagal Upload (Kredensial hilang / API limit / File error)
                    # Beri hukuman penalti (bisa juga 0 jika tidak ingin menghancurkan skor topik terlalu cepat)
                    reward = -2.0
                    logger.warning(f"⚠️ Gagal mengunggah ke YouTube. REWARD -2.0")

            else:
                 logger.warning(f"⚠️ Gagal merender video. REWARD -2.0")

            # Cleanup source video
            downloader.cleanup(video_path)
        else:
             logger.warning(f"⚠️ Gagal mengunduh bahan baku video. REWARD -2.0")

        # Update Skor Topik di Memory
        if is_new_topic:
            old_score = 15.0
            times_chosen = 1
        else:
            current_data = redis_client.get_topic_score(selected_topic)
            old_score = current_data.get("score", 0.0)
            times_chosen = current_data.get("times_chosen", 0) + 1

        alpha = 0.3
        new_score = old_score + alpha * (reward - old_score)

        redis_client.set_topic_score(selected_topic, new_score, times_chosen)
        logger.info(f"📈 Skor topik '{selected_topic}' diupdate: {old_score:.2f} -> {new_score:.2f} (Dipilih {times_chosen}x)")

        self.state = self._update_state()
        self.current_step += 1

        if self.current_step >= 10:
             done = True

        return self.state, reward, done, False, info

    def render(self):
        logger.info(f"State saat ini: {dict(zip(self.topics, self.state[:-1]))}")
