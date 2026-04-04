import os
import whisper
import torch
from logger import logger

# Whisper memanggil ffmpeg via subprocess untuk decode audio.
# Jika ffmpeg tidak ada di PATH Windows, inject dari imageio_ffmpeg (bundled).
try:
    import imageio_ffmpeg

    _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    _ffmpeg_dir = os.path.dirname(_ffmpeg_exe)
    if _ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    logger.info("🛠️ FFmpeg terdeteksi via imageio: %s", _ffmpeg_exe)
except Exception as e:
    logger.warning("⚠️ Gagal menginjeksi FFmpeg: %s", e)

from transformers import pipeline
from typing import Any, Dict, cast, List


class AIEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🔄 Menginisialisasi model AI pada device: {self.device}")

        # Inisialisasi Whisper
        try:
            self.whisper_model = whisper.load_model("base", device=self.device)
            logger.info("✅ Whisper (base) berhasil dimuat.")
        except Exception as e:
            logger.error(f"❌ Gagal memuat Whisper: {e}")
            self.whisper_model = None

        # Inisialisasi mDeBERTa untuk zero-shot classification (Smart CTA)
        try:
            # Gunakan penugasan tipe Any untuk mematikan validasi overload Pyright yang membingungkan
            pipeline_func: Any = pipeline
            self.mdeberta_pipeline = pipeline_func(
                task="zero-shot-classification",
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                token=os.getenv("HF_TOKEN"),
                device=0 if self.device == "cuda" else -1,
            )
            logger.info("✅ mDeBERTa (MoritzLaurer) berhasil dimuat.")
        except Exception as e:
            logger.error("❌ Gagal memuat mDeBERTa: %s", e)
            self.mdeberta_pipeline = None

        # Inisialisasi IndoBERT untuk sentimen evaluasi (Simulasi Reward UGC)
        try:
            pipeline_func: Any = pipeline
            self.indobert_pipeline = pipeline_func(
                task="sentiment-analysis",
                model="mdhugol/indonesia-bert-sentiment-classification",
                token=os.getenv("HF_TOKEN"),
                device=0 if self.device == "cuda" else -1,
            )
            logger.info(
                "✅ IndoBERT (indobenchmark) berhasil dimuat untuk Analisis Sentimen."
            )
        except Exception as e:
            logger.error("❌ Gagal memuat IndoBERT: %s", e)
            self.indobert_pipeline = None

    def transcribe_audio(self, audio_path: str):
        if not self.whisper_model:
            logger.error("⚠️ Whisper tidak tersedia.")
            return []

        logger.info(f"🎙️ Memulai transkripsi: {audio_path}")
        try:
            # Pastikan FFmpeg dalam PATH sesaat sebelum transkripsi (Windows Fix)
            import imageio_ffmpeg
            ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
            if ffmpeg_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

            # Whisper memanggil ffmpeg via subprocess
            try:
                # Cast result to Dict for type safety as Whisper returns Any/Generic
                result_raw = self.whisper_model.transcribe(
                    audio_path, word_timestamps=True
                )
                result = cast(Dict[str, Any], result_raw)
            except FileNotFoundError as e:
                if "ffmpeg" in str(e).lower():
                    logger.error("❌ Whisper gagal: FFmpeg tidak ditemukan di sistem!")
                    logger.info(
                        "💡 SOLUSI: Pastikan FFmpeg terinstal atau imageio_ffmpeg berhasil diinjeksi ke PATH."
                    )
                raise e

            words_data: List[Dict[str, Any]] = []
            for segment in result.get("segments", []):
                for word in segment.get("words", []):
                    words_data.append(
                        {
                            "word": word["word"].strip(),
                            "start": word["start"],
                            "end": word["end"],
                        }
                    )
            logger.info("✅ Transkripsi selesai. %d kata diekstrak.", len(words_data))
            return words_data
        except Exception as e:
            logger.error(f"❌ Transkripsi gagal: {e}")
            return []

    def generate_smart_cta(self, transcript_text: str):
        if not self.mdeberta_pipeline:
            logger.warning("⚠️ mDeBERTa tidak tersedia. Menggunakan CTA default.")
            return "Komen pendapatmu di bawah!"

        if not transcript_text or len(transcript_text.strip()) < 10:
            return "Bagaimana menurutmu? Komen ya!"

        logger.info("🧠 Menganalisis teks untuk Smart CTA...")
        candidate_labels = [
            "bertanya pendapat",
            "mengundang debat",
            "meminta saran",
            "berbagi pengalaman",
            "menyatakan fakta mengejutkan",
        ]

        try:
            text_to_analyze = (
                transcript_text[-1000:]
                if len(transcript_text) > 1000
                else transcript_text
            )
            result = self.mdeberta_pipeline(text_to_analyze, candidate_labels)
            top_label = result["labels"][0]

            cta_mapping = {
                "bertanya pendapat": "Gimana pendapatmu? Setuju nggak? Komen!",
                "mengundang debat": "Coba bantah ini di kolom komentar!",
                "meminta saran": "Punya tips lain? Share di komentar!",
                "berbagi pengalaman": "Pernah ngalamin ini? Ceritain dong!",
                "menyatakan fakta mengejutkan": "Mindblowing kan? Komen reaksi kalian!",
            }

            cta_text = cta_mapping.get(
                top_label, "Menurut kamu gimana? Komen di bawah!"
            )
            logger.info(
                f"✅ Smart CTA dihasilkan: '{cta_text}' (Kategori: {top_label})"
            )
            return cta_text
        except Exception as e:
            logger.error(f"❌ Smart CTA gagal: {e}")
            return "Drop komentar kalian di bawah!"

    def generate_quiz_question(self, transcript_text: str):
        if not self.mdeberta_pipeline:
            logger.warning("⚠️ mDeBERTa tidak tersedia. Menggunakan kuis default.")
            return "Tebak apa rahasia mengejutkan ini? Waktu kalian 5 detik..."

        if not transcript_text or len(transcript_text.strip()) < 10:
            return "Tebak apa rahasia ini? Waktu kalian 5 detik..."

        logger.info("🧠 Menganalisis teks untuk Pertanyaan Kuis...")
        # Simplifikasi logika "ekstrak inti jawaban" menjadi memicu rasa penasaran
        candidate_labels = [
            "mengungkap fakta",
            "strategi rahasia",
            "kesalahan fatal",
            "tips sukses",
        ]

        try:
            text_to_analyze = transcript_text[:1000]  # Analisis dari awal
            result = self.mdeberta_pipeline(text_to_analyze, candidate_labels)
            top_label = result["labels"][0]

            kuis_mapping = {
                "mengungkap fakta": "Tebak apa fakta mengejutkan dari opini ini? Waktu kalian 5 detik...",
                "strategi rahasia": "Tebak apa strategi rahasia orang ini? Waktu kalian 5 detik...",
                "kesalahan fatal": "Tebak apa kesalahan fatal yang dia bahas? Waktu kalian 5 detik...",
                "tips sukses": "Tebak apa tips sukses utama di video ini? Waktu kalian 5 detik...",
            }

            kuis_text = kuis_mapping.get(
                top_label,
                "Tebak apa inti rahasia dari video ini? Waktu kalian 5 detik...",
            )
            logger.info(
                f"✅ Pertanyaan Kuis dihasilkan: '{kuis_text}' (Kategori: {top_label})"
            )
            return kuis_text
        except Exception as e:
            logger.error(f"❌ Generate Pertanyaan Kuis gagal: {e}")
            return "Tebak apa hal penting yang dibahas ini? Waktu kalian 5 detik..."

    def evaluate_sentiment(self, texts: list):
        """Mengevaluasi sentimen teks UGC (misal simulasi komentar) menggunakan IndoBERT"""
        if not self.indobert_pipeline:
            return 0.0  # Neutral fallback

        logger.info("🧠 Menganalisis Sentimen Komentar (IndoBERT)...")
        score = 0.0
        try:
            # IndoBERT pipeline return LABEL_0 (negative), LABEL_1 (neutral), LABEL_2 (positive)
            # (Atau variasi lain tergantung model, tapi indobenchmark umumnya klasifikasi multi class)
            # Demi penyederhanaan pipeline default HF untuk sentimen:
            results = self.indobert_pipeline(texts)
            for res in results:
                label = res["label"].lower()
                # Mapping label secara umum
                if "positive" in label or "1" in label or "2" in label:
                    score += 2.0
                elif "negative" in label or "0" in label:
                    score -= 1.5
                else:
                    score += 0.5  # Neutral
            avg_score = score / len(texts) if texts else 0.0
            logger.info(
                f"✅ Sentimen terukur. Rata-rata Skor Berbasis Sentimen: {avg_score:.2f}"
            )
            return avg_score
        except Exception as e:
            logger.error(f"❌ Evaluasi sentimen gagal: {e}")
            return 0.0


ai_engine = AIEngine()
