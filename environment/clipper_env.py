import gymnasium as gym
from gymnasium import spaces
import numpy as np
import datetime
from logger import logger
from data.redis_client import redis_client
from data.mongodb_client import db
from data.models import PublishedVideo
from core.downloader import downloader
from core.editor import video_editor
from core.knowledge import knowledge_base
from core.researcher import get_trending_topic
from core.uploader_yt import youtube_uploader
from core.uploader_ig import ig_uploader
from core.comment_generator import generate_provocative_comment
from core.ai_models import ai_engine
from typing import Optional


class ContentCreatorEnv(gym.Env):
    """
    God-Tier Environment: Agen memilih (Topik + Profil Visual).
    Dilengkapi Spider Coordination untuk menghindari duplikasi antar worker.
    Reward dihitung berdasarkan simulasi Analisis Sentimen IndoBERT terhadap konten.

    NEW: Self-Correction & Pivot Logic
    - Setiap step() dimulai dengan memeriksa performa video 24-48 jam lalu.
    - Jika ditemukan video LOW_VIEWS → aktifkan Aggressive Mode secara otomatis.
    - Aggressive Mode: penalti topik di Redis, force pivot topik+visual, upload konten lebih agresif.
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

    def _save_published_video(
        self,
        topic_name: str,
        video_url: str,
        platform: str,
        platform_video_id: Optional[str] = None,
    ):
        try:
            new_video = PublishedVideo(
                platform=platform,
                topic_name=topic_name,
                video_url=video_url,
                views=0,
                performance_status="PENDING",
                platform_video_id=platform_video_id,
            )
            # MongoDB Insert
            db.published_videos.insert_one(new_video.to_dict())
            logger.info(f"💾 Disimpan ke MongoDB ({platform}): {video_url}")
        except Exception as e:
            logger.error(f"❌ Gagal menyimpan PublishedVideo ke MongoDB: {e}")

    def _check_last_performance(self) -> dict:
        """
        Cek performa video yang dipublish dalam 24-48 jam terakhir.
        Jika ditemukan video dengan status LOW_VIEWS, aktifkan Self-Correction Mode.

        Returns dict:
            {
                "is_aggressive"   : bool  - True jika ada video LOW_VIEWS
                "failed_topics"   : list  - Topik yang gagal (untuk dihindari/dipenalti)
                "failed_profiles" : list  - Design profile idx yang gagal
                "fresh_topic"     : str   - Topik yang paling jarang dipilih (force pick)
            }
        """
        result: dict = {
            "is_aggressive": False,
            "failed_topics": [],
            "failed_profiles": [],
            "fresh_topic": None,
        }

        try:
            # Window evaluasi: video yang sudah lebih dari 24 jam dipublish
            window_start = datetime.datetime.utcnow() - datetime.timedelta(hours=48)
            window_end = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

            # Query MongoDB: Filter berdasarkan rentang waktu dan status
            low_videos_data = db.published_videos.find({
                "published_at": {"$gte": window_start, "$lte": window_end},
                "performance_status": "LOW_VIEWS"
            })
            
            low_videos = [PublishedVideo.from_dict(v) for v in low_videos_data]

            if not low_videos:
                return result  # Semua baik-baik saja

            result["is_aggressive"] = True
            logger.warning(
                f"⚠️  [SELF-CORRECTION] Ditemukan {len(low_videos)} video LOW_VIEWS! "
                f"Mengaktifkan Aggressive Mode & Pivot..."
            )

            for v in low_videos:
                topic_name_str: str = str(v.topic_name)
                result["failed_topics"].append(topic_name_str)
                logger.warning(
                    f"   📉 '{topic_name_str}' | views={v.views} | platform={v.platform}"
                )

                # Berikan penalti pada topik yang gagal di Redis
                try:
                    current = redis_client.get_topic_score(topic_name_str)
                    old_score: float = current.get("score", 0.0)
                    times_chosen: int = current.get("times_chosen", 0)
                    penalized_score = old_score - 5.0
                    redis_client.set_topic_score(topic_name_str, penalized_score, times_chosen)
                    logger.warning(
                        f"   🔴 Penalti score '{topic_name_str}': {old_score:.2f} → {penalized_score:.2f}"
                    )
                except Exception as redis_err:
                    logger.error(f"❌ Gagal update penalti Redis: {redis_err}")

            # Cari topik yang paling jarang dipilih sebagai fresh topic
            try:
                all_topics = redis_client.get_all_topics()
                if all_topics:
                    unused_topics = [
                        t for t in all_topics
                        if t["name"] not in result["failed_topics"]
                    ]
                    if unused_topics:
                        sorted_topics = sorted(
                            unused_topics, key=lambda t: t.get("times_chosen", 0)
                        )
                        result["fresh_topic"] = sorted_topics[0]["name"]
                        logger.info(
                            f"✨ [PIVOT] Fresh topic dipilih: '{result['fresh_topic']}' "
                            f"(times_chosen={sorted_topics[0].get('times_chosen', 0)})"
                        )
            except Exception as topic_err:
                logger.error(f"❌ Gagal cari fresh topic: {topic_err}")

        except Exception as e:
            logger.error(f"❌ [SELF-CORRECTION] Gagal cek performa DB: {e}")

        return result

    def step(self, action_idx):
        if action_idx >= self.num_actions:
            raise ValueError(f"Action index out of bounds")

        # ======================================================================
        # SELF-CORRECTION CHECK: Baca performa video 24-48 jam lalu.
        # Jika ada yang LOW_VIEWS → aktifkan Aggressive Mode & Force Pivot.
        # ======================================================================
        perf_check = self._check_last_performance()
        is_aggressive: bool = perf_check["is_aggressive"]
        fresh_topic: str = perf_check.get("fresh_topic") or ""

        if is_aggressive:
            logger.warning(
                f"🔄 [SELF-CORRECTION] Mode Agresif AKTIF. "
                f"Force pivot ke topik fresh: '{fresh_topic or 'EKSPLORASI'}'."
            )
        # ======================================================================

        selected_topic, visual_idx = self._decode_action(action_idx)
        is_explore_action = selected_topic == "EKSPLORASI"
        is_new_topic = False

        # Jika aggressive mode: override topik ke fresh_topic jika topik saat ini adalah low-performer
        if is_aggressive and fresh_topic and not is_explore_action:
            if selected_topic in perf_check["failed_topics"]:
                logger.info(
                    f"🔄 [PIVOT] Topik '{selected_topic}' adalah low-performer. "
                    f"Override ke '{fresh_topic}'."
                )
                selected_topic = fresh_topic

        # Force pivot design profile: jika aggressive dan visual 0, ganti ke 1 (lebih kontras)
        if is_aggressive and visual_idx == 0:
            visual_idx = 1
            logger.info("🎨 [PIVOT] Design profile di-override: 0 (Kuning-Hitam) → 1 (Putih-Merah)")

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
                visual_idx = 0

        # --- SPIDER NETWORK COORDINATION ---
        if redis_client.is_task_active(selected_topic) and not is_explore_action:
            logger.warning(
                f"🕸️ SPIDER COLLISION: '{selected_topic}' sedang digarap worker lain! Agen mengalah."
            )
            redis_client.set_topic_score(selected_topic, -0.5, 0)
            return (
                self._update_state(),
                -0.5,
                False,
                False,
                {"success": False, "collision": True},
            )

        redis_client.add_active_task(selected_topic)

        logger.info(
            f"🤖 [STEP {self.current_step}] Memproses: '{selected_topic}' | "
            f"Profil Visual: {visual_idx} | Aggressive: {is_aggressive}"
        )

        reward = -2.0
        done = False
        info = {
            "topic": selected_topic,
            "success": False,
            "url_yt": None,
            "url_ig": None,
            "is_aggressive": is_aggressive,
        }

        try:
            edit_result = None
            video_path = None

            if visual_idx == 0:
                # 0: Standar Hormozi
                logger.info("🎬 Menggunakan Format 0: Standar Hormozi")
                video_path = downloader.search_and_download(selected_topic)
                if video_path:
                    edit_result = video_editor.process_video(
                        video_path, 0, is_aggressive=is_aggressive
                    )

            elif visual_idx == 1:
                # 1: Clash of Titans
                logger.info("⚔️ Menggunakan Format 1: Clash of Titans")
                clip_pro_path = downloader.search_and_download(f"{selected_topic} pro")
                clip_con_path = downloader.search_and_download(f"{selected_topic} kontra")

                if not clip_pro_path and clip_con_path:
                    clip_pro_path = downloader.search_and_download(selected_topic)
                if not clip_con_path and clip_pro_path:
                    clip_con_path = downloader.search_and_download(selected_topic)

                if clip_pro_path and clip_con_path:
                    edit_result = video_editor.create_clash_format(clip_pro_path, clip_con_path)
                    video_path = [clip_pro_path, clip_con_path]
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
                    import os as _os
                    import uuid
                    import moviepy.editor as mp

                    try:
                        temp_video = mp.VideoFileClip(video_path)
                        try:
                            dur = min(15, temp_video.duration)
                            temp_clip = temp_video.subclip(0, dur)
                            temp_audio = f"data/output/temp_audio_analyze_{uuid.uuid4().hex[:4]}.wav"
                            temp_clip.audio.write_audiofile(
                                temp_audio, fps=16000, nbytes=2, buffersize=2000, logger=None
                            )
                            words_data = ai_engine.transcribe_audio(temp_audio)
                            transcript_text = " ".join([w["word"] for w in words_data])
                            if _os.path.exists(temp_audio):
                                _os.remove(temp_audio)
                        finally:
                            logger.info("Closing temp_video")
                            temp_video.close()

                        pertanyaan_kuis = ai_engine.generate_quiz_question(transcript_text)
                    except Exception as e:
                        logger.error(f"❌ Gagal mengekstrak transkrip untuk kuis: {e}")
                        pertanyaan_kuis = (
                            f"Tebak apa rahasia dari {selected_topic}? Waktu kalian 5 detik..."
                        )

                    edit_result = video_editor.create_quiz_format(pertanyaan_kuis, video_path)

            if edit_result:
                description: str = edit_result.get("transcript", "")
                output_video_path = edit_result.get("output_path")
                cta_used: str = edit_result.get("cta_used", "")

                # 1. EVALUASI SENTIMEN IndoBERT (Simulasi UGC Reward)
                sentiment_score = ai_engine.evaluate_sentiment(
                    [cta_used, description[:200]]
                )
                reward = 1.0 + sentiment_score
                logger.info(f"📊 Evaluasi Sentimen UGC selesai. Reward Akhir: {reward:.2f}")

                knowledge_base.extract_and_save(selected_topic, edit_result, reward=reward)

                title = f"{selected_topic.capitalize()} | Opini UGC Viral"
                tags = [
                    "UGC",
                    selected_topic.replace(" ", ""),
                    "Viral",
                    "Opini",
                    "Indonesia",
                    "Trending",
                    "Shorts",
                    "Reels",
                    "TikTok",
                    "hot",
                    "sensasi",
                ]

                # 2. SISTEM DISTRIBUSI ANTREAN (STAGGERED UPLOAD)
                from data.models import UploadQueue
                try:
                    now_utc = datetime.datetime.utcnow()
                    
                    platforms = [
                        ("youtube", 0),
                        ("instagram", 30),
                        ("facebook", 60),
                        ("tiktok", 120)
                    ]

                    for plat, delay in platforms:
                        desc = description
                        if plat == "instagram":
                            desc = f"{title}\n\n{cta_used}\n\n#reelsindonesia #viral"
                        elif plat == "facebook":
                            desc = f"{title}\n\n{cta_used}"
                        elif plat == "tiktok":
                            desc = f"{title} 🔥 #fyp #indonesia #viral"

                        q_item = UploadQueue(
                            platform=plat,
                            video_path=str(output_video_path),
                            title=title,
                            description=desc,
                            tags=",".join(tags),
                            topic_name=selected_topic,
                            scheduled_at=now_utc + datetime.timedelta(minutes=delay)
                        )
                        db.upload_queue.insert_one(q_item.to_dict())

                    logger.info("📋 4 Tugas Upload (YT, IG, FB, TT) telah masuk antrean (Staggered/MongoDB).")
                    info["success"] = True
                except Exception as qe:
                    logger.error(f"❌ Gagal antrekan upload: {qe}")
                # Sistem antrean berhasil dijadwalkan
                pass

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

        # Update Skor Topik di Redis
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
