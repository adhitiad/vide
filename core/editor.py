import os
import asyncio
import glob
import random

# Gunakan pola pencarian cerdas jika versi ImageMagick berubah di masa depan (Windows fix)
_im_paths = glob.glob(r"C:\Program Files\ImageMagick*\magick.exe")
if _im_paths:
    os.environ["IMAGEMAGICK_BINARY"] = _im_paths[0]

import cv2
import moviepy.editor as mp
import moviepy.video.fx.all as vfx
import moviepy.audio.fx.all as afx
from moviepy.video.fx.resize import resize as mp_resize
from moviepy.audio.AudioClip import CompositeAudioClip
from logger import logger
import numpy as np

# Integrasi Rust (PyO3) - Opsional
try:
    import vide_performa
    HAS_RUST_PERFORMA = True
    logger.info("⚡ Modul Performa Rust (PyO3) terdeteksi! Menggunakan akselerasi hardware.")
except ImportError:
    HAS_RUST_PERFORMA = False
    logger.info("ℹ️ Modul Performa Rust tidak ditemukan. Menggunakan mode standar Python.")

from utils.ffmpeg_async import extract_audio_async, run_ffmpeg_async

# Emoji yang disisipkan secara acak pada subtitle mode agresif
_AGGRESSIVE_EMOJIS = ["⚠️", "🔥", "💀", "😤", "❗"]

# Global placeholder for MediaPipe solution
mp_face_detection = None
HAS_MEDIAPIPE = False

try:
    import mediapipe as mp_base
    if hasattr(mp_base, "solutions"):
        # Coba import secara langsung untuk mendukung linter dan runtime
        try:
            from mediapipe.solutions import face_detection
            mp_face_detection = face_detection
        except (ImportError, AttributeError):
            from mediapipe.python.solutions import face_detection as mp_face_detection
            
        if mp_face_detection is not None:
            HAS_MEDIAPIPE = True
except (ImportError, AttributeError, ModuleNotFoundError, Exception):
    HAS_MEDIAPIPE = False

if not HAS_MEDIAPIPE:
    logger.warning(
        "⚠️ MediaPipe tidak kompatibel atau tidak ditemukan. Face Tracking dinonaktifkan."
    )
import os
import uuid
from .ai_models import ai_engine
from .voice import voice_engine


class VideoEditor:
    def __init__(self, output_dir="data/output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.font = "Impact"

        # A/B Testing Profiles untuk Subtitle Visual
        self.design_profiles = [
            {"name": "Kuning-Hitam", "color": "yellow", "stroke": "black", "size": 75},
            {"name": "Putih-Merah", "color": "white", "stroke": "red", "size": 70},
            {"name": "Hijau-Hacker", "color": "lime", "stroke": "black", "size": 65},
        ]

    def _autocrop_face_tracking(
        self, video_clip: mp.VideoFileClip, target_w=720, target_h=1280
    ):
        """
        Autocrop 2.0 (Face-Tracking): Melacak wajah di tiap frame.
        Jika tidak ada wajah, potong statis di tengah.
        """
        logger.info("👀 Memulai Face Tracking (Autocrop 2.0)...")
        w, h = video_clip.size

        # Gunakan fungsi resize yang diimpor langsung untuk kompatibilitas linter
        if w / h <= target_w / target_h:
            return video_clip.fx(mp_resize, width=target_w, height=target_h)

        if not HAS_MEDIAPIPE:
            logger.info("ℹ️ Fallback Center Crop aktif (MediaPipe offline).")
            # Langsung bypass ke fallback di blok except bawah dengan cara return yang sama
            return self._fallback_center_crop(video_clip, target_w, target_h)

        try:
            # mp_face_detection sudah di-import di tingkat modul jika HAS_MEDIAPIPE True
            # Gunakan resolusi kecil untuk tracking agar tidak lambat
            small_w, small_h = 320, int(h * (320 / w))

            # Inisialisasi FaceDetection sekali di luar loop frame untuk performa
            if mp_face_detection is None:
                raise ImportError("MediaPipe face_detection module is None")
                
            face_detection = mp_face_detection.FaceDetection(
                model_selection=1, min_detection_confidence=0.5
            )

            # State tracking to only detect face every 0.5s for performance boost
            track_state = {"x": w // 2, "time": -1.0}

            def crop_frame(get_frame, t):
                frame = get_frame(t)

                # Batasi x_center agar tidak crop ke luar batas
                target_ratio = target_w / target_h
                crop_w = int(h * target_ratio)

                # Default (Tengah)
                x_center = w // 2

                # Coba deteksi wajah setiap detik untuk optimasi
                # Karena moviepy get_frame berjalan per frame, tracking per frame sangat lambat.
                # Bolt Optimization: Reuse face position periodically to massively speed up rendering
                if t - track_state["time"] >= 0.5:
                    small_frame = cv2.resize(frame, (small_w, small_h))
                    results = face_detection.process(
                        cv2.cvtColor(small_frame, cv2.COLOR_RGB2BGR)
                    )

                    if results.detections:
                        # Ambil wajah pertama
                        bbox = results.detections[0].location_data.relative_bounding_box
                        x_center_rel = bbox.xmin + (bbox.width / 2)
                        
                        # GUNAKAN RUST JIKA TERSEDIA untuk kalkulasi koordinat presisi
                        if HAS_RUST_PERFORMA:
                            try:
                                # Simulasi pemanggilan Rust (vide_performa mengembalikan koordinat mentah)
                                import json
                                res_json = vide_performa.calculate_crop_windows(
                                    w, h, target_w, target_h, [(t, x_center_rel)]
                                )
                                windows = json.loads(res_json)
                                track_state["x"] = windows[0]["x1"] + (crop_w // 2) if windows else int(x_center_rel * h)
                            except Exception:
                                track_state["x"] = int(x_center_rel * w)
                        else:
                            track_state["x"] = int(x_center_rel * w)
                            
                    track_state["time"] = t

                x1 = max(0, x_center - crop_w // 2)
                x2 = min(w, x1 + crop_w)

                # Sesuaikan x1 jika x2 mentok batas
                if x2 == w:
                    x1 = max(0, w - crop_w)

                cropped = frame[:, x1:x2]
                return cv2.resize(cropped, (target_w, target_h))

            # Terapkan transformasi (Peringatan: ini sangat berat karena dieksekusi per frame)
            # Untuk skenario production, biasanya orang hanya mendeteksi 1 wajah di frame awal
            # atau melakukan sliding window (pans) per scene.
            # Demi instruksi "Face-Tracking", kita aplikasikan fl_image.
            logger.info(
                "⏳ Melakukan Frame-by-Frame Face Tracking Crop (mungkin butuh waktu lama)..."
            )
            tracked_clip = video_clip.fl(lambda gf, t: crop_frame(gf, t))

            # Tutup FaceDetection saat clip selesai untuk membebaskan memory
            # Karena moviepy bersifat lazy, kita pasang hook close pada clip
            original_close = tracked_clip.close

            def close_all():
                try:
                    face_detection.close()
                finally:
                    original_close()

            tracked_clip.close = close_all

            return tracked_clip

        except Exception as e:
            logger.error(
                f"❌ Autocrop Face-Tracking gagal, fallback ke crop tengah: {e}"
            )
            return self._fallback_center_crop(video_clip, target_w, target_h)

    def _fallback_center_crop(
        self, video_clip: mp.VideoFileClip, target_w=720, target_h=1280
    ):
        w, h = video_clip.size
        target_ratio = target_w / target_h
        crop_w = int(h * target_ratio)
        x_center = w / 2
        x1 = max(0, x_center - crop_w / 2)
        x2 = min(w, x1 + crop_w)
        # Gunakan vfx.crop jika tersedia, jika tidak fallback ke method .crop()
        try:
            return video_clip.fx(vfx.crop, x1=x1, y1=0, x2=x2, y2=h).fx(mp_resize, newsize=(target_w, target_h))
        except Exception:
            # Fallback untuk versi MoviePy lama atau jika fx gagal
            return video_clip.crop(x1=x1, y1=0, x2=x2, y2=h).resize(newsize=(target_w, target_h))

    def _create_hormozi_subtitle(
        self, word_data, video_width, video_height, profile, is_aggressive: bool = False
    ):
        """
        Membuat subtitle beranimasi berdasarkan profil desain A/B Testing.

        Args:
            is_aggressive: Jika True, sisipkan emoji ⚠️/🔥 secara acak pada 30% kata
                           untuk menciptakan efek urgensi visual (Self-Correction Mode).
        """
        txt_clips = []
        for idx, w in enumerate(word_data):
            word = w["word"].upper()
            start, end = w["start"], w["end"]
            duration = end - start
            if duration <= 0:
                continue

            # Mode Agresif: randomisasi sisipan emoji pada ~30% kata
            if is_aggressive and random.random() < 0.30:
                emoji = random.choice(_AGGRESSIVE_EMOJIS)
                word = f"{emoji} {word}" if random.random() < 0.5 else f"{word} {emoji}"

            try:
                txt_clip = mp.TextClip(
                    word,
                    fontsize=profile["size"],
                    color=profile["color"],
                    font=self.font,
                    stroke_color=profile["stroke"],
                    stroke_width=3,
                    method="caption",
                    size=(video_width - 100, None),
                    align="center",
                )
                txt_clip = (
                    txt_clip.set_position(("center", "center"))
                    .set_start(start)
                    .set_duration(duration)
                )
                txt_clips.append(txt_clip)
            except Exception:
                pass
        return txt_clips

    def _create_smart_cta(
        self, cta_text, video_width, video_height, start_time, duration=3
    ):
        try:
            bg_height = int(video_height * 0.15)
            bg_clip = mp.ColorClip(size=(video_width, bg_height), color=(255, 0, 0))
            bg_clip = bg_clip.set_opacity(0.85).set_position(
                ("center", video_height - bg_height - 50)
            )
            bg_clip = bg_clip.set_start(start_time).set_duration(duration)

            txt_clip = mp.TextClip(
                cta_text,
                fontsize=60,
                color="white",
                font=self.font,
                stroke_color="black",
                stroke_width=2,
                method="caption",
                size=(video_width - 40, bg_height),
                align="center",
            )
            txt_clip = txt_clip.set_position(("center", video_height - bg_height - 50))
            txt_clip = txt_clip.set_start(start_time).set_duration(duration)
            txt_clip = txt_clip.fx(vfx.blink, d_on=0.5, d_off=0.2)

            return [bg_clip, txt_clip]
        except Exception as e:
            return []

    def _create_flash_frame(self, video_width, video_height, start_time, duration=0.15):
        try:
            flash_bg = mp.ColorClip(size=(video_width, video_height), color=(0, 0, 0))
            flash_bg = (
                flash_bg.set_position(("center", "center"))
                .set_start(start_time)
                .set_duration(duration)
            )

            flash_txt = mp.TextClip(
                "TONTON ULANG!",
                fontsize=100,
                color="red",
                font=self.font,
                stroke_color="white",
                stroke_width=5,
            )
            flash_txt = (
                flash_txt.set_position(("center", "center"))
                .set_start(start_time)
                .set_duration(duration)
            )

            return [flash_bg, flash_txt]
        except Exception as e:
            return []

    def create_clash_format(self, clip_pro_path: str, clip_con_path: str) -> dict:
        """Membuat format Clash of Titans (Split-Screen)"""
        logger.info(f"⚔️ Memulai pembuatan format Clash of Titans...")
        output_filename = f"clash_of_titans_{uuid.uuid4().hex[:6]}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            # 1. Muat Video
            clip_pro = mp.VideoFileClip(clip_pro_path)
            clip_con = mp.VideoFileClip(clip_con_path)

            # Batasi durasi agar tidak terlalu panjang (misal 30 detik tiap klip)
            max_dur = min(30, clip_pro.duration, clip_con.duration)
            clip_pro = clip_pro.subclip(0, max_dur)
            clip_con = clip_con.subclip(0, max_dur)

            target_w, target_h = 1080, 960

            # 2. Crop dan Resize masing-masing klip
            clip_pro = self._autocrop_face_tracking(clip_pro, target_w, target_h)
            clip_con = self._autocrop_face_tracking(clip_con, target_w, target_h)

            # 3. Transkripsi untuk subtitle bergantian
            temp_audio_pro = f"temp_audio_pro_{uuid.uuid4().hex[:4]}.wav"
            temp_audio_con = f"temp_audio_con_{uuid.uuid4().hex[:4]}.wav"

            clip_pro.audio.write_audiofile(
                temp_audio_pro, fps=16000, nbytes=2, buffersize=2000, logger=None
            )
            clip_con.audio.write_audiofile(
                temp_audio_con, fps=16000, nbytes=2, buffersize=2000, logger=None
            )

            words_pro = ai_engine.transcribe_audio(temp_audio_pro)
            words_con = ai_engine.transcribe_audio(temp_audio_con)

            if os.path.exists(temp_audio_pro):
                os.remove(temp_audio_pro)
            if os.path.exists(temp_audio_con):
                os.remove(temp_audio_con)

            # Buat teks subtitle untuk kedua belah pihak
            profile = self.design_profiles[0]  # Default profile

            # Subtitle Pro (Atas)
            txt_clips_pro = []
            for w in words_pro:
                duration = w["end"] - w["start"]
                if duration > 0:
                    try:
                        t_clip = mp.TextClip(
                            w["word"].upper(),
                            fontsize=profile["size"],
                            color=profile["color"],
                            font=self.font,
                            stroke_color=profile["stroke"],
                            stroke_width=3,
                            method="caption",
                            size=(target_w - 100, None),
                            align="center",
                        )
                        # Posisi relatif di dalam klip atas (h=960, posisi tengah bawah)
                        t_clip = (
                            t_clip.set_position(("center", 700))
                            .set_start(w["start"])
                            .set_duration(duration)
                        )
                        txt_clips_pro.append(t_clip)
                    except Exception:
                        pass

            # Gabungkan subtitle pro ke klip pro
            clip_pro = mp.CompositeVideoClip([clip_pro] + txt_clips_pro)

            # Karena durasi gabungan ini serentak (atas bawah bicara sama-sama?),
            # untuk efek Clash, klip_con (Bawah) akan disesuaikan timeline-nya agar bergantian.
            # Agar sederhana dan mengikuti instruksi:
            # "Gabungkan secara vertikal menggunakan clips_array([[clip_pro], [clip_con]])."
            # dan "saat atas bicara, bawah diam/di-mute, dan sebaliknya."
            # Kita susun secara sekuensial durasinya.

            # Menyusun agar bergantian:
            # Clip Pro main duluan (durasi clip_pro), clip con di-freeze.
            # Lalu Clip Con main (durasi clip_con), clip pro di-freeze.

            pro_final_dur = clip_pro.duration
            con_final_dur = clip_con.duration
            total_dur = pro_final_dur + con_final_dur

            # Freeze frames
            freeze_pro = clip_pro.to_ImageClip(t=clip_pro.duration - 0.1).set_duration(
                con_final_dur
            )
            freeze_con = clip_con.to_ImageClip(t=0).set_duration(pro_final_dur)

            # Urutan Pro
            pro_part = mp.concatenate_videoclips([clip_pro, freeze_pro])

            # Urutan Con: diam saat pro main, lalu main dengan subtitlenya.
            # Subtitle Con (Bawah)
            txt_clips_con = []
            for w in words_con:
                duration = w["end"] - w["start"]
                if duration > 0:
                    try:
                        # Waktu start digeser karena clip_con main setelah clip_pro
                        t_clip = mp.TextClip(
                            w["word"].upper(),
                            fontsize=profile["size"],
                            color=profile["color"],
                            font=self.font,
                            stroke_color=profile["stroke"],
                            stroke_width=3,
                            method="caption",
                            size=(target_w - 100, None),
                            align="center",
                        )
                        t_clip = (
                            t_clip.set_position(("center", 700))
                            .set_start(pro_final_dur + w["start"])
                            .set_duration(duration)
                        )
                        txt_clips_con.append(t_clip)
                    except Exception:
                        pass

            # Clip con delay audio dan video
            # Freeze con di depan, clip con di belakang
            con_part = mp.concatenate_videoclips([freeze_con, clip_con]).set_audio(
                mp.CompositeAudioClip([clip_con.audio.set_start(pro_final_dur)])
            )
            con_part = mp.CompositeVideoClip([con_part] + txt_clips_con)

            # 4. Gabungkan secara vertikal menggunakan clips_array
            final_video = mp.clips_array([[pro_part], [con_part]])
            # Gabungkan audio dari kedua bagian
            final_audio = mp.CompositeAudioClip([pro_part.audio, con_part.audio])
            final_video = final_video.set_audio(final_audio)

            # 5. Buat TextClip garis pemisah di tengah
            divider_bg = mp.ColorClip(size=(target_w, 150), color=(255, 0, 0))
            divider_bg = divider_bg.set_position(("center", 960 - 75)).set_duration(
                total_dur
            )

            divider_txt = mp.TextClip(
                "SIAPA YANG BENAR? 👇",
                fontsize=80,
                color="white",
                font=self.font,
                stroke_color="black",
                stroke_width=4,
            )
            divider_txt = divider_txt.set_position(("center", 960 - 50)).set_duration(
                total_dur
            )

            # Gabungkan dengan garis pemisah
            final_video = mp.CompositeVideoClip([final_video, divider_bg, divider_txt])
            final_video = final_video.set_duration(total_dur)

            logger.info("⚙️ Merender Mahakarya Video (Clash of Titans Edition)...")
            final_video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                threads=4,
                logger=None,
            )

            clip_pro.close()
            clip_con.close()
            final_video.close()

            # Gabungkan transcript
            full_text = (
                " ".join([w["word"] for w in words_pro])
                + " "
                + " ".join([w["word"] for w in words_con])
            )

            return {
                "output_path": output_path,
                "transcript": full_text,
                "cta_used": "Siapa yang paling benar menurut kalian? Komen di bawah!",
                "duration": total_dur,
                "design_profile": "Clash of Titans",
            }
        except Exception as e:
            logger.error(f"❌ Kesalahan pada create_clash_format: {e}")
            return {"error": str(e)}

    def create_quiz_format(self, pertanyaan_kuis: str, video_utama_path: str) -> dict:
        """Membuat Retention Trap (Quiz Format)"""
        logger.info(f"❓ Memulai pembuatan format Retention Trap (Quiz)...")
        output_filename = f"retention_trap_{uuid.uuid4().hex[:6]}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            target_w, target_h = 720, 1280

            # 1. Buat intro 5 detik
            intro_bg = mp.ColorClip(
                size=(target_w, target_h), color=(20, 20, 20)
            ).set_duration(5)

            # Pertanyaan
            txt_pertanyaan = mp.TextClip(
                pertanyaan_kuis,
                fontsize=70,
                color="yellow",
                font=self.font,
                stroke_color="black",
                stroke_width=3,
                method="caption",
                size=(target_w - 60, None),
                align="center",
            )
            txt_pertanyaan = txt_pertanyaan.set_position(
                ("center", "center")
            ).set_duration(5)

            # Countdown
            countdowns = []
            for i in range(5):
                num_txt = mp.TextClip(
                    str(5 - i),
                    fontsize=150,
                    color="red",
                    font=self.font,
                    stroke_color="white",
                    stroke_width=5,
                )
                num_txt = (
                    num_txt.set_position(("center", target_h - 300))
                    .set_start(i)
                    .set_duration(1)
                )
                countdowns.append(num_txt)

            intro_clip = mp.CompositeVideoClip([intro_bg, txt_pertanyaan] + countdowns)

            # 2. Proses video utama (seperti biasa)
            video_utama = mp.VideoFileClip(video_utama_path)
            max_dur = min(55, video_utama.duration)
            video_utama = video_utama.subclip(0, max_dur)
            video_utama = self._autocrop_face_tracking(video_utama, target_w, target_h)

            temp_audio = f"temp_audio_quiz_{uuid.uuid4().hex[:4]}.wav"
            video_utama.audio.write_audiofile(
                temp_audio, fps=16000, nbytes=2, buffersize=2000, logger=None
            )
            words_data = ai_engine.transcribe_audio(temp_audio)
            if os.path.exists(temp_audio):
                os.remove(temp_audio)

            profile = self.design_profiles[1]  # Pakai profil 1 misalnya
            subtitle_clips = self._create_hormozi_subtitle(
                words_data, target_w, target_h, profile
            )

            video_utama_with_subs = mp.CompositeVideoClip(
                [video_utama] + subtitle_clips
            ).set_duration(max_dur)

            # 3. Gabungkan intro dan video utama
            final_video = mp.concatenate_videoclips([intro_clip, video_utama_with_subs])

            logger.info("⚙️ Merender Mahakarya Video (Quiz Retention Trap Edition)...")
            final_video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                threads=4,
                logger=None,
            )

            video_utama.close()
            final_video.close()

            full_text = " ".join([w["word"] for w in words_data])

            return {
                "output_path": output_path,
                "transcript": full_text,
                "cta_used": pertanyaan_kuis,
                "duration": final_video.duration,
                "design_profile": "Retention Trap (Quiz)",
            }

        except Exception as e:
            logger.error(f"❌ Kesalahan pada create_quiz_format: {e}")
            return {"error": str(e)}

    def process_video(
        self,
        input_path: str,
        design_profile_idx: int = 0,
        is_aggressive: bool = False,
    ) -> dict:
        """
        Memproses UGC Skala Studio (Face-Tracking, Voice-Over AI Ducking, A/B Testing Visual).

        Args:
            design_profile_idx: Index profil desain (0=Kuning-Hitam, 1=Putih-Merah, 2=Hijau-Hacker)
            is_aggressive      : Jika True (Self-Correction Mode):
                                   - Audio hook 3 detik pertama di-speed-up 1.1x (efek urgensi)
                                   - Emoji ⚠️/🔥 disisipkan acak di subtitle
                                   - Design profile di-swap ke profile paling berbeda
        """
        logger.info(
            f"🎬 Memulai produksi {'🔥 AGGRESSIVE' if is_aggressive else 'Studio-Grade'}: {input_path}"
        )

        # Profiling design
        profile = self.design_profiles[design_profile_idx % len(self.design_profiles)]
        logger.info(f"🎨 Visual Profile: {profile['name']}")

        output_filename = f"god_tier_{uuid.uuid4().hex[:6]}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            # 1. Muat Video Asli dan potong ke 60 detik maksimal
            video = mp.VideoFileClip(input_path)
            max_duration = 60
            if video.duration > max_duration:
                # Ambil 60 detik tengah yang kemungkinan paling intens (UGC Podcast)
                start_cut = min(video.duration / 3, video.duration - max_duration)
                video = video.subclip(start_cut, start_cut + max_duration)

            actual_duration = video.duration
            target_w, target_h = 720, 1280

            # 2. Face-Tracking Autocrop
            video = self._autocrop_face_tracking(video, target_w, target_h)

            # 3. Transkripsi dengan Whisper (Gunakan Async FFmpeg untuk ekstraksi audio)
            temp_audio_path = f"temp_audio_{uuid.uuid4().hex[:4]}.wav"
            
            # Optimalisasi Asynchronous: Ganti video.audio.write_audiofile yang blocking
            logger.info("⚡ Mengekstrak audio secara asynchronous...")
            # Kita panggil loop async dalam thread sinkron ini (worker thread)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(extract_audio_async(input_path, temp_audio_path))
            loop.close()

            if not success:
                logger.error("❌ Gagal mengekstrak audio via Async FFmpeg, fallback ke sync.")
                video.audio.write_audiofile(
                    temp_audio_path, fps=16000, nbytes=2, buffersize=2000, logger=None
                )

            words_data = ai_engine.transcribe_audio(temp_audio_path)
            full_text = " ".join([w["word"] for w in words_data])

            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

            # 4. Generate AI Voice-Over Hook (ElevenLabs)
            # Ambil ~8 kata pertama sebagai intro script (atau generate dari LLM, di sini kita rangkum otomatis)
            intro_words = words_data[:10]
            intro_text = "Dengarkan opini panas ini! " + " ".join(
                [w["word"] for w in intro_words]
            )

            hook_audio_path = voice_engine.generate_hook_audio(intro_text)

            # 5. Audio Ducking (Gabungkan Voice Hook AI dengan Audio Asli)
            final_audio = video.audio
            if hook_audio_path:
                try:
                    hook_clip = mp.AudioFileClip(hook_audio_path)

                    # ── MODE AGRESIF: Speed-up audio hook 1.1x di 3 detik pertama ────────
                    # Efek psikologis: kecepatan lebih tinggi = persepsi urgensi dan energi
                    if is_aggressive:
                        try:
                            # Gunakan speedx (bukan audio_speedx) untuk moviepy audio fx
                            hook_clip = hook_clip.fx(afx.speedx, 1.1)
                            logger.info(
                                "⚡ [AGGRESSIVE] Audio hook di-speed-up 1.1x untuk efek urgensi."
                            )
                        except Exception as spd_err:
                            logger.warning(
                                f"⚠️ Gagal speed-up audio, pakai kecepatan normal: {spd_err}"
                            )
                    # ─────────────────────────────────────────────────────────────────────

                    hook_dur = hook_clip.duration

                    # Turunkan volume audio asli sebesar 50% selama durasi hook (Ducking)
                    original_ducked = video.audio.subclip(0, hook_dur).volumex(0.3)
                    original_rest = video.audio.subclip(hook_dur, actual_duration)

                    # Gabungkan Voice Hook dengan Original Ducked
                    mixed_hook_segment = CompositeAudioClip(
                        [original_ducked, hook_clip]
                    )
                    final_audio = mp.concatenate_audioclips(
                        [mixed_hook_segment, original_rest]
                    )
                    logger.info("🔊 Ducking Audio dan AI Hook berhasil disematkan!")
                except Exception as e:
                    logger.error(f"❌ Gagal menyematkan Audio Hook: {e}")

            video = video.set_audio(final_audio)

            # 6. Pembuatan Layer Visual
            subtitle_clips = self._create_hormozi_subtitle(
                words_data, target_w, target_h, profile, is_aggressive=is_aggressive
            )

            cta_text = ai_engine.generate_smart_cta(full_text)
            cta_clips = self._create_smart_cta(
                cta_text, target_w, target_h, max(0, actual_duration - 3), 3
            )
            flash_clips = self._create_flash_frame(
                target_w, target_h, max(0, actual_duration - 0.15), 0.15
            )

            # Gabungkan layer
            final_video = mp.CompositeVideoClip(
                [video] + subtitle_clips + cta_clips + flash_clips
            )
            final_video = final_video.set_duration(actual_duration)

            # 7. Render Akhir
            logger.info("⚙️ Merender Mahakarya Video (God-Tier Edition)...")
            final_video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                threads=4,
                logger=None,
            )

            video.close()
            final_video.close()
            if hook_audio_path and os.path.exists(hook_audio_path):
                os.remove(hook_audio_path)

            return {
                "output_path": output_path,
                "transcript": full_text,
                "cta_used": cta_text,
                "duration": actual_duration,
                "design_profile": profile["name"],
                "is_aggressive": is_aggressive,
            }

        except Exception as e:
            logger.error(f"❌ Kesalahan Studio Editing: {e}")
            return {"error": str(e)}


video_editor = VideoEditor()
