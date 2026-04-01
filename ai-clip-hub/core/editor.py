import moviepy.editor as mp
import moviepy.video.fx.all as vfx
from logger import logger
import os
import uuid
from .ai_models import ai_engine

class VideoEditor:
    def __init__(self, output_dir="data/output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        # Font default, bisa disesuaikan dengan OS
        self.font = "Impact"

    def _create_hormozi_subtitle(self, word_data, video_width, video_height):
        """Membuat subtitle per kata beranimasi (Hormozi style)"""
        txt_clips = []
        # Tambahkan margin aman
        safe_margin_y = video_height * 0.15

        for w in word_data:
            word = w["word"].upper()
            start = w["start"]
            end = w["end"]
            duration = end - start

            if duration <= 0:
                 continue

            # Warna acak untuk penekanan pada kata-kata penting (simulasi sederhana)
            color = 'yellow' if len(word) > 5 else 'white'
            stroke_color = 'black'
            stroke_width = 3

            try:
                txt_clip = mp.TextClip(
                    word,
                    fontsize=75,
                    color=color,
                    font=self.font,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    method='caption',
                    size=(video_width - 100, None),
                    align='center'
                )

                # Posisi di tengah layar agak ke bawah
                txt_clip = txt_clip.set_position(('center', 'center'))
                txt_clip = txt_clip.set_start(start).set_duration(duration)

                # Animasi sederhana: Pop-up effect (scale up)
                # Catatan: resize fx lambat di moviepy 1.0.3, kita skip efek rumit agar cepat
                # txt_clip = txt_clip.resize(lambda t: min(1, 0.8 + 2*t))

                txt_clips.append(txt_clip)
            except Exception as e:
                logger.warning(f"⚠️ Gagal merender kata '{word}': {e}")

        return txt_clips

    def _create_smart_cta(self, cta_text, video_width, video_height, start_time, duration=3):
        """Membuat banner CTA di akhir video"""
        try:
            # Banner Background
            bg_height = int(video_height * 0.15)
            bg_clip = mp.ColorClip(size=(video_width, bg_height), color=(255, 0, 0)) # Merah
            bg_clip = bg_clip.set_opacity(0.85)
            bg_clip = bg_clip.set_position(('center', video_height - bg_height - 50))
            bg_clip = bg_clip.set_start(start_time).set_duration(duration)

            # Teks CTA
            txt_clip = mp.TextClip(
                cta_text,
                fontsize=60,
                color='white',
                font=self.font,
                stroke_color='black',
                stroke_width=2,
                method='caption',
                size=(video_width - 40, bg_height),
                align='center'
            )
            txt_clip = txt_clip.set_position(('center', video_height - bg_height - 50))
            txt_clip = txt_clip.set_start(start_time).set_duration(duration)

            # Efek berkedip sederhana untuk menarik perhatian
            txt_clip = txt_clip.fx(vfx.blink, d_on=0.5, d_off=0.2)

            return [bg_clip, txt_clip]
        except Exception as e:
            logger.error(f"❌ Gagal membuat Smart CTA: {e}")
            return []

    def _create_flash_frame(self, video_width, video_height, start_time, duration=0.15):
        """Menambahkan frame flash di detik terakhir untuk memicu rewatch (TikTok hack)"""
        try:
            flash_bg = mp.ColorClip(size=(video_width, video_height), color=(0, 0, 0))
            flash_bg = flash_bg.set_position(('center', 'center')).set_start(start_time).set_duration(duration)

            flash_txt = mp.TextClip(
                "TONTON ULANG!",
                fontsize=100,
                color='red',
                font=self.font,
                stroke_color='white',
                stroke_width=5
            )
            flash_txt = flash_txt.set_position(('center', 'center')).set_start(start_time).set_duration(duration)

            return [flash_bg, flash_txt]
        except Exception as e:
            logger.warning(f"⚠️ Gagal membuat Flash Frame: {e}")
            return []

    def process_video(self, input_path: str) -> dict:
        """Memotong, merender rasio 9:16, menambah subtitle & CTA"""
        logger.info(f"🎬 Memulai proses editing video: {input_path}")

        output_filename = f"short_{uuid.uuid4().hex[:6]}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            # 1. Muat Video
            video = mp.VideoFileClip(input_path)

            # Potong 60 detik pertama jika lebih panjang (untuk Shorts/Reels)
            max_duration = 60
            if video.duration > max_duration:
                # Ambil segmen menarik (misal dari detik 30 hingga 90, atau awal)
                start_cut = min(30, video.duration - max_duration)
                video = video.subclip(start_cut, start_cut + max_duration)
                logger.info(f"✂️ Memotong video menjadi {max_duration} detik.")

            actual_duration = video.duration

            # 2. Crop ke Rasio 9:16 (Vertikal)
            w, h = video.size
            target_ratio = 9 / 16

            # Hitung crop (tengah)
            if w / h > target_ratio: # Video Landscape (16:9)
                new_w = int(h * target_ratio)
                x_center = w / 2
                video = video.crop(x1=x_center - new_w/2, y1=0, x2=x_center + new_w/2, y2=h)

            # Resize standar Shorts (1080x1920) jika memori cukup,
            # tapi 720x1280 lebih cepat dan stabil
            target_w, target_h = 720, 1280
            video = video.resize(newsize=(target_w, target_h))

            # 3. Ekstrak Audio untuk Transkripsi (sementara)
            temp_audio_path = f"temp_audio_{uuid.uuid4().hex[:4]}.wav"
            video.audio.write_audiofile(temp_audio_path, fps=16000, nbytes=2, buffersize=2000, logger=None)

            # 4. Transkripsi Audio dengan Whisper
            words_data = ai_engine.transcribe_audio(temp_audio_path)

            # Ekstrak full text untuk mDeBERTa
            full_text = " ".join([w["word"] for w in words_data])

            # Hapus audio sementara
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

            # 5. Buat Subtitle Clips
            subtitle_clips = self._create_hormozi_subtitle(words_data, target_w, target_h)

            # 6. Smart CTA (3 detik terakhir)
            cta_text = ai_engine.generate_smart_cta(full_text)
            cta_start_time = max(0, actual_duration - 3)
            cta_clips = self._create_smart_cta(cta_text, target_w, target_h, cta_start_time, duration=3)

            # 7. Flash Frame Hack (0.15 detik terakhir)
            flash_start = max(0, actual_duration - 0.15)
            flash_clips = self._create_flash_frame(target_w, target_h, flash_start, duration=0.15)

            # Gabungkan semua layer
            final_clips = [video] + subtitle_clips + cta_clips + flash_clips

            final_video = mp.CompositeVideoClip(final_clips)
            final_video = final_video.set_duration(actual_duration)

            # 8. Render Video
            logger.info("⚙️ Merender video akhir...")
            # Gunakan parameter optimasi untuk kecepatan (ultrafast)
            final_video.write_videofile(
                output_path,
                fps=30,
                codec='libx264',
                audio_codec='aac',
                preset='ultrafast',
                threads=4,
                logger=None # Matikan log moviepy
            )

            # Tutup resources
            video.close()
            final_video.close()

            logger.info(f"✅ Video berhasil diproses: {output_path}")

            return {
                "output_path": output_path,
                "transcript": full_text,
                "cta_used": cta_text,
                "duration": actual_duration
            }

        except Exception as e:
            logger.error(f"❌ Kesalahan saat mengedit video: {e}")
            return None

video_editor = VideoEditor()
