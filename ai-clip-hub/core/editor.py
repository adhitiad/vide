import moviepy.editor as mp
import moviepy.video.fx.all as vfx
from moviepy.audio.AudioClip import CompositeAudioClip
import numpy as np
import cv2
import mediapipe as mp_face
from logger import logger
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
            {"name": "Hijau-Hacker", "color": "lime", "stroke": "black", "size": 65}
        ]

    def _autocrop_face_tracking(self, video_clip: mp.VideoFileClip, target_w=720, target_h=1280):
        """
        Autocrop 2.0 (Face-Tracking): Melacak wajah di tiap frame.
        Jika tidak ada wajah, potong statis di tengah.
        """
        logger.info("👀 Memulai Face Tracking (Autocrop 2.0)...")
        w, h = video_clip.size

        # Jika video sudah vertikal atau mendekati vertikal, cukup resize
        if w / h <= target_w / target_h:
            return video_clip.resize(newsize=(target_w, target_h))

        mp_face_detection = mp_face.solutions.face_detection

        try:
            # Gunakan resolusi kecil untuk tracking agar tidak lambat
            small_w, small_h = 320, int(h * (320 / w))

            def crop_frame(get_frame, t):
                frame = get_frame(t)

                # Default (Tengah)
                x_center = w // 2

                # Coba deteksi wajah setiap detik untuk optimasi
                # Karena moviepy get_frame berjalan per frame, tracking per frame sangat lambat.
                # Sebagai kompromi, kita pakai MediaPipe pada frame yang di-resize
                with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
                    small_frame = cv2.resize(frame, (small_w, small_h))
                    results = face_detection.process(cv2.cvtColor(small_frame, cv2.COLOR_RGB2BGR))

                    if results.detections:
                        # Ambil wajah pertama
                        bbox = results.detections[0].location_data.relative_bounding_box
                        x_center_rel = bbox.xmin + (bbox.width / 2)
                        x_center = int(x_center_rel * w)

                # Batasi x_center agar tidak crop ke luar batas
                target_ratio = target_w / target_h
                crop_w = int(h * target_ratio)

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
            logger.info("⏳ Melakukan Frame-by-Frame Face Tracking Crop (mungkin butuh waktu lama)...")
            tracked_clip = video_clip.fl(lambda gf, t: crop_frame(gf, t))
            return tracked_clip

        except Exception as e:
            logger.error(f"❌ Autocrop Face-Tracking gagal, fallback ke crop tengah: {e}")
            target_ratio = target_w / target_h
            crop_w = int(h * target_ratio)
            x_center = w / 2
            x1 = max(0, x_center - crop_w / 2)
            x2 = min(w, x1 + crop_w)
            return video_clip.crop(x1=x1, y1=0, x2=x2, y2=h).resize(newsize=(target_w, target_h))

    def _create_hormozi_subtitle(self, word_data, video_width, video_height, profile):
        """Membuat subtitle beranimasi berdasarkan profil desain A/B Testing"""
        txt_clips = []
        for w in word_data:
            word = w["word"].upper()
            start, end = w["start"], w["end"]
            duration = end - start
            if duration <= 0: continue

            try:
                txt_clip = mp.TextClip(
                    word,
                    fontsize=profile["size"],
                    color=profile["color"],
                    font=self.font,
                    stroke_color=profile["stroke"],
                    stroke_width=3,
                    method='caption',
                    size=(video_width - 100, None),
                    align='center'
                )
                txt_clip = txt_clip.set_position(('center', 'center')).set_start(start).set_duration(duration)
                txt_clips.append(txt_clip)
            except Exception as e:
                pass
        return txt_clips

    def _create_smart_cta(self, cta_text, video_width, video_height, start_time, duration=3):
        try:
            bg_height = int(video_height * 0.15)
            bg_clip = mp.ColorClip(size=(video_width, bg_height), color=(255, 0, 0))
            bg_clip = bg_clip.set_opacity(0.85).set_position(('center', video_height - bg_height - 50))
            bg_clip = bg_clip.set_start(start_time).set_duration(duration)

            txt_clip = mp.TextClip(
                cta_text, fontsize=60, color='white', font=self.font,
                stroke_color='black', stroke_width=2, method='caption',
                size=(video_width - 40, bg_height), align='center'
            )
            txt_clip = txt_clip.set_position(('center', video_height - bg_height - 50))
            txt_clip = txt_clip.set_start(start_time).set_duration(duration)
            txt_clip = txt_clip.fx(vfx.blink, d_on=0.5, d_off=0.2)

            return [bg_clip, txt_clip]
        except Exception as e:
            return []

    def _create_flash_frame(self, video_width, video_height, start_time, duration=0.15):
        try:
            flash_bg = mp.ColorClip(size=(video_width, video_height), color=(0, 0, 0))
            flash_bg = flash_bg.set_position(('center', 'center')).set_start(start_time).set_duration(duration)

            flash_txt = mp.TextClip("TONTON ULANG!", fontsize=100, color='red', font=self.font, stroke_color='white', stroke_width=5)
            flash_txt = flash_txt.set_position(('center', 'center')).set_start(start_time).set_duration(duration)

            return [flash_bg, flash_txt]
        except Exception as e:
            return []

    def process_video(self, input_path: str, design_profile_idx: int = 0) -> dict:
        """Memproses UGC Skala Studio (Face-Tracking, Voice-Over AI Ducking, A/B Testing Visual)"""
        logger.info(f"🎬 Memulai produksi Studio-Grade: {input_path}")

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

            # 3. Transkripsi dengan Whisper
            temp_audio_path = f"temp_audio_{uuid.uuid4().hex[:4]}.wav"
            video.audio.write_audiofile(temp_audio_path, fps=16000, nbytes=2, buffersize=2000, logger=None)
            words_data = ai_engine.transcribe_audio(temp_audio_path)
            full_text = " ".join([w["word"] for w in words_data])

            if os.path.exists(temp_audio_path): os.remove(temp_audio_path)

            # 4. Generate AI Voice-Over Hook (ElevenLabs)
            # Ambil ~8 kata pertama sebagai intro script (atau generate dari LLM, di sini kita rangkum otomatis)
            intro_words = words_data[:10]
            intro_text = "Dengarkan opini panas ini! " + " ".join([w["word"] for w in intro_words])

            hook_audio_path = voice_engine.generate_hook_audio(intro_text)

            # 5. Audio Ducking (Gabungkan Voice Hook AI dengan Audio Asli)
            final_audio = video.audio
            if hook_audio_path:
                try:
                    hook_clip = mp.AudioFileClip(hook_audio_path)
                    hook_dur = hook_clip.duration

                    # Turunkan volume audio asli sebesar 50% selama durasi hook (Ducking)
                    # Karena moviepy CompositeAudioClip menumpuk audio, kita pisahkan segmen
                    original_ducked = video.audio.subclip(0, hook_dur).volumex(0.3)
                    original_rest = video.audio.subclip(hook_dur, actual_duration)

                    # Gabungkan Voice Hook dengan Original Ducked
                    mixed_hook_segment = CompositeAudioClip([original_ducked, hook_clip])
                    final_audio = mp.concatenate_audioclips([mixed_hook_segment, original_rest])
                    logger.info("🔊 Ducking Audio dan AI Hook berhasil disematkan!")
                except Exception as e:
                    logger.error(f"❌ Gagal menyematkan Audio Hook: {e}")

            video = video.set_audio(final_audio)

            # 6. Pembuatan Layer Visual
            subtitle_clips = self._create_hormozi_subtitle(words_data, target_w, target_h, profile)

            cta_text = ai_engine.generate_smart_cta(full_text)
            cta_clips = self._create_smart_cta(cta_text, target_w, target_h, max(0, actual_duration - 3), 3)
            flash_clips = self._create_flash_frame(target_w, target_h, max(0, actual_duration - 0.15), 0.15)

            # Gabungkan layer
            final_video = mp.CompositeVideoClip([video] + subtitle_clips + cta_clips + flash_clips)
            final_video = final_video.set_duration(actual_duration)

            # 7. Render Akhir
            logger.info("⚙️ Merender Mahakarya Video (God-Tier Edition)...")
            final_video.write_videofile(
                output_path, fps=30, codec='libx264', audio_codec='aac',
                preset='ultrafast', threads=4, logger=None
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
                "design_profile": profile["name"]
            }

        except Exception as e:
            logger.error(f"❌ Kesalahan Studio Editing: {e}")
            return None

video_editor = VideoEditor()
