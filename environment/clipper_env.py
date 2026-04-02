import gymnasium as gym
from gymnasium import spaces
import numpy as np
from logger import logger
from data.redis_client import redis_client
from data.database import SessionLocal
from data.models import PublishedVideo
from core.downloader import downloader
from core.editor import video_editor
from core.knowledge import knowledge_base
from core.researcher import get_trending_topic
from core.uploader_yt import youtube_uploader
from core.uploader_ig import ig_uploader
from core.comment_generator import generate_provocative_comment
from core.ai_models import ai_engine


class ContentCreatorEnv(gym.Env):
    """
    God-Tier Environment: Agen memilih (Topik + Profil Visual).
    Dilengkapi Spider Coordination untuk menghindari duplikasi antar worker.
    Reward dihitung berdasarkan simulasi Analisis Sentimen IndoBERT terhadap konten.
    """

    metadata = {"render_modes": ["console"]}

    def __init__(self):
        super(ContentCreatorEnv, self).__init__()

        # 1. Action Space
        self.topics = self._get_active_topics()
        self.visual_profiles = (
            3  # 0: Standar Hormozi, 1: Clash of Titans, 2: Quiz Retention Trap
        )

        # Action space = (Num_Topics * 3 Visuals) + 1 Aksi Riset
        # Total kombinasi unik yang bisa dieksploitasi
        self.num_actions = (len(self.topics) * self.visual_profiles) + 1
        self.action_space = spaces.Discrete(self.num_actions)

        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(self.num_actions,), dtype=np.float32
        )

        self.state = np.zeros(self.num_actions)
        self.current_step = 0

        logger.info(
            f"🌍 God-Tier RL Environment: {len(self.topics)} Topik x {self.visual_profiles} Desain Visual."
        )

    def _get_active_topics(self):
        topics_data = redis_client.get_all_topics()
        return [t["name"] for t in topics_data] if topics_data else []

    def _decode_action(self, action_idx):
        """Menerjemahkan integer action menjadi (Topic, Visual_Profile_Idx)"""
        if action_idx == self.num_actions - 1:
            return "EKSPLORASI", -1

        topic_idx = action_idx // self.visual_profiles
        visual_idx = action_idx % self.visual_profiles
        return self.topics[topic_idx], visual_idx

    def _update_state(self):
        self.state = np.zeros(self.num_actions)

        for i, topic in enumerate(self.topics):
            data = redis_client.get_topic_score(topic)
            base_score = data.get("score", 0.0)

            # Kita bagi base_score secara seragam ke tiap variasi visual (sebagai simplifikasi)
            # Idealnya, DB menyimpan skor per kombinasi (Topik+Visual), tapi untuk menjaga
            # skema DB sederhana, kita tambahkan noise/varians agar agen tetap eksplor visual
            for v in range(self.visual_profiles):
                action_idx = (i * self.visual_profiles) + v
                self.state[action_idx] = base_score + (0.1 * v)

        self.state[-1] = 0.0  # Skor Eksplorasi Riset
        return self.state

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0

        self.topics = self._get_active_topics()
        self.num_actions = (len(self.topics) * self.visual_profiles) + 1
        self.action_space = spaces.Discrete(self.num_actions)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(self.num_actions,), dtype=np.float32
        )

        state = self._update_state()
        return state, {}

    def _save_published_video(self, topic_name: str, video_url: str, platform: str):
        session = SessionLocal()
        try:
            new_video = PublishedVideo(
                platform=platform, topic_name=topic_name, video_url=video_url, views=0
            )
            session.add(new_video)
            session.commit()
            logger.info(f"💾 Disimpan ke DB ({platform}): {video_url}")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Gagal menyimpan PublishedVideo: {e}")
        finally:
            session.close()

    def step(self, action_idx):
        if action_idx >= self.num_actions:
            raise ValueError(f"Action index out of bounds")

        selected_topic, visual_idx = self._decode_action(action_idx)
        is_explore_action = selected_topic == "EKSPLORASI"
        is_new_topic = False

        if is_explore_action:
            selected_topic = get_trending_topic()
            existing_topics_lower = [t.lower() for t in self.topics]
            if selected_topic.lower() not in existing_topics_lower:
                logger.info(f"✨ Menambahkan topik viral baru: '{selected_topic}'")
                is_new_topic = True
                self.topics.append(selected_topic)

                self.num_actions = (len(self.topics) * self.visual_profiles) + 1
                self.action_space = spaces.Discrete(self.num_actions)
                self.observation_space = spaces.Box(
                    low=-np.inf,
                    high=np.inf,
                    shape=(self.num_actions,),
                    dtype=np.float32,
                )
                # Secara default, eksplorasi menggunakan profil visual 0
                visual_idx = 0

        # --- SPIDER NETWORK COORDINATION ---
        # Cek apakah topik ini sedang digarap oleh worker lain di cluster
        if redis_client.is_task_active(selected_topic) and not is_explore_action:
            logger.warning(
                f"🕸️ SPIDER COLLISION: '{selected_topic}' sedang digarap worker lain! Agen mengalah dan memilih topik lain."
            )
            # Beri penalti ringan agar agen tidak stuck memilih ini terus di loop saat ini
            redis_client.set_topic_score(selected_topic, -0.5, 0)
            return (
                self._update_state(),
                -0.5,
                False,
                False,
                {"success": False, "collision": True},
            )

        # Kunci topik ini di Redis
        redis_client.add_active_task(selected_topic)

        logger.info(
            f"🤖 [STEP {self.current_step}] Memproses: '{selected_topic}' | Profil Visual: {visual_idx}"
        )

        reward = -2.0
        done = False
        info = {
            "topic": selected_topic,
            "success": False,
            "url_yt": None,
            "url_ig": None,
        }

        try:
            edit_result = None
            video_path = None

            if visual_idx == 0:
                # 0: Standar Hormozi
                logger.info("🎬 Menggunakan Format 0: Standar Hormozi")
                video_path = downloader.search_and_download(selected_topic)
                if video_path:
                    edit_result = video_editor.process_video(video_path, 0)

            elif visual_idx == 1:
                # 1: Clash of Titans
                logger.info("⚔️ Menggunakan Format 1: Clash of Titans")
                # Unduh 2 klip dengan pandangan berbeda
                clip_pro_path = downloader.search_and_download(f"{selected_topic} pro")
                clip_con_path = downloader.search_and_download(
                    f"{selected_topic} kontra"
                )

                # Fallback jika tidak dapat 2 video
                if not clip_pro_path and clip_con_path:
                    clip_pro_path = downloader.search_and_download(selected_topic)
                if not clip_con_path and clip_pro_path:
                    clip_con_path = downloader.search_and_download(selected_topic)

                if clip_pro_path and clip_con_path:
                    edit_result = video_editor.create_clash_format(
                        clip_pro_path, clip_con_path
                    )
                    video_path = [clip_pro_path, clip_con_path]  # Untuk cleanup
                else:
                    logger.error("❌ Gagal mengunduh bahan untuk Clash of Titans")
                    if clip_pro_path:
                        downloader.cleanup(clip_pro_path)
                    if clip_con_path:
                        downloader.cleanup(clip_con_path)

            elif visual_idx == 2:
                # 2: Quiz Retention Trap
                logger.info("❓ Menggunakan Format 2: Quiz Retention Trap")
                video_path = downloader.search_and_download(selected_topic)
                if video_path:
                    # Transkrip sebagian untuk mDeBERTa
                    import os, uuid
                    import moviepy.editor as mp

                    try:
                        temp_video = mp.VideoFileClip(video_path)
                        # Ambil 15 detik pertama untuk analisa
                        dur = min(15, temp_video.duration)
                        temp_clip = temp_video.subclip(0, dur)
                        temp_audio = (
                            f"data/output/temp_audio_analyze_{uuid.uuid4().hex[:4]}.wav"
                        )
                        temp_clip.audio.write_audiofile(
                            temp_audio,
                            fps=16000,
                            nbytes=2,
                            buffersize=2000,
                            logger=None,
                        )
                        words_data = ai_engine.transcribe_audio(temp_audio)
                        transcript_text = " ".join([w["word"] for w in words_data])

                        if os.path.exists(temp_audio):
                            os.remove(temp_audio)
                        temp_video.close()

                        pertanyaan_kuis = ai_engine.generate_quiz_question(
                            transcript_text
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Gagal mengekstrak transkrip untuk pertanyaan kuis: {e}"
                        )
                        pertanyaan_kuis = f"Tebak apa rahasia dari {selected_topic}? Waktu kalian 5 detik..."

                    edit_result = video_editor.create_quiz_format(
                        pertanyaan_kuis, video_path
                    )

            if edit_result:
                description = edit_result.get("transcript", "")
                output_video_path = edit_result.get("output_path")
                cta_used = edit_result.get("cta_used", "")

                # 1. EVALUASI SENTIMEN IndoBERT (Simulasi UGC Reward)
                # Kita asumsikan transcript/CTA memancing sentimen audiens.
                # Jika kalimat memancing debat/reaksi kuat, reward bertambah.
                sentiment_score = ai_engine.evaluate_sentiment(
                    [cta_used, description[:200]]
                )
                # Base reward + Sentiment Evaluation (-1.5 s/d +2.0)
                reward = 1.0 + sentiment_score
                logger.info(
                    f"📊 Evaluasi Sentimen UGC selesai. Reward Akhir: {reward:.2f}"
                )

                knowledge_base.extract_and_save(
                    selected_topic, edit_result, reward=reward
                )

                title = f"{selected_topic.capitalize()} | Opini UGC Viral"
                tags = [
                    "UGC",
                    selected_topic.replace(" ", ""),
                    "Viral",
                    "Opini",
                    "Indonesia",
                ]

                # 2. DISTRIBUSI: YouTube & Instagram
                # Generate komentar provokatif via LangChain
                provocative_comment = generate_provocative_comment(
                    description, selected_topic
                )

                yt_url = youtube_uploader.upload_to_youtube_shorts(
                    output_video_path,
                    title,
                    description,
                    tags,
                    comment_text=provocative_comment,
                )
                if yt_url:
                    info["url_yt"] = yt_url
                    self._save_published_video(selected_topic, yt_url, "youtube")
                else:
                    reward -= 1.0  # Penalti karena gagal YT

                ig_caption = f"{title}\n\n{cta_used}\n\n#reelsindonesia #viral"
                ig_url = ig_uploader.upload_to_reels(output_video_path, ig_caption)
                if ig_url:
                    info["url_ig"] = ig_url
                    self._save_published_video(selected_topic, ig_url, "instagram")
                else:
                    pass  # IG sering strict, jangan hukum agen terlalu berat

                if yt_url or ig_url:
                    info["success"] = True

            if video_path:
                if isinstance(video_path, list):
                    for vp in video_path:
                        downloader.cleanup(vp)
                else:
                    downloader.cleanup(video_path)

        except Exception as e:
            logger.error(f"❌ Kesalahan Fatal dalam Pipeline RL: {e}")
            reward = -2.0

        finally:
            # Lepaskan kunci Spider Network
            redis_client.remove_active_task(selected_topic)

        # Update Skor Topik
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

        self.state = self._update_state()
        self.current_step += 1

        if self.current_step >= 10:
            done = True

        return self.state, reward, done, False, info

    def render(self):
        pass
