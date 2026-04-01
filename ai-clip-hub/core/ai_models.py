import whisper
from transformers import pipeline
from logger import logger
import torch

class AIEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🔄 Menginisialisasi model AI pada device: {self.device}")

        # Inisialisasi Whisper
        try:
            # Menggunakan whisper-base untuk kecepatan dan word-level ASR
            self.whisper_model = whisper.load_model("base", device=self.device)
            logger.info("✅ Whisper (base) berhasil dimuat.")
        except Exception as e:
            logger.error(f"❌ Gagal memuat Whisper: {e}")
            self.whisper_model = None

        # Inisialisasi mDeBERTa untuk zero-shot classification (Smart CTA)
        try:
            self.mdeberta_pipeline = pipeline(
                "zero-shot-classification",
                model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
                device=0 if self.device == "cuda" else -1
            )
            logger.info("✅ mDeBERTa (MoritzLaurer) berhasil dimuat.")
        except Exception as e:
            logger.error(f"❌ Gagal memuat mDeBERTa: {e}")
            self.mdeberta_pipeline = None

    def transcribe_audio(self, audio_path: str):
        """Transkripsi audio dengan timestamp per kata menggunakan Whisper"""
        if not self.whisper_model:
            logger.error("⚠️ Whisper tidak tersedia.")
            return []

        logger.info(f"🎙️ Memulai transkripsi: {audio_path}")
        try:
            # Word-level timestamp didukung secara native oleh Whisper versi baru
            # (jika menggunakan openai-whisper)
            result = self.whisper_model.transcribe(audio_path, word_timestamps=True)

            words_data = []
            for segment in result.get("segments", []):
                for word in segment.get("words", []):
                    words_data.append({
                        "word": word["word"].strip(),
                        "start": word["start"],
                        "end": word["end"]
                    })

            logger.info(f"✅ Transkripsi selesai. {len(words_data)} kata diekstrak.")
            return words_data

        except Exception as e:
            logger.error(f"❌ Transkripsi gagal: {e}")
            return []

    def generate_smart_cta(self, transcript_text: str):
        """Menghasilkan Smart CTA menggunakan mDeBERTa (Zero-shot)"""
        if not self.mdeberta_pipeline:
            logger.warning("⚠️ mDeBERTa tidak tersedia. Menggunakan CTA default.")
            return "Komen pendapatmu di bawah!"

        if not transcript_text or len(transcript_text.strip()) < 10:
             return "Bagaimana menurutmu? Komen ya!"

        logger.info("🧠 Menganalisis teks untuk Smart CTA...")

        # Kategori intensi untuk memancing komentar
        candidate_labels = ["bertanya pendapat", "mengundang debat", "meminta saran", "berbagi pengalaman", "menyatakan fakta mengejutkan"]

        try:
            # Truncate teks agar tidak melebihi batas token model
            # Fokus pada 1000 karakter terakhir dari video (karena CTA di akhir)
            text_to_analyze = transcript_text[-1000:] if len(transcript_text) > 1000 else transcript_text

            result = self.mdeberta_pipeline(text_to_analyze, candidate_labels)
            top_label = result['labels'][0]

            # Mapping label ke pertanyaan CTA
            cta_mapping = {
                "bertanya pendapat": "Gimana pendapatmu? Setuju nggak? Komen!",
                "mengundang debat": "Coba bantah ini di kolom komentar!",
                "meminta saran": "Punya tips lain? Share di komentar!",
                "berbagi pengalaman": "Pernah ngalamin ini? Ceritain dong!",
                "menyatakan fakta mengejutkan": "Mindblowing kan? Komen reaksi kalian!"
            }

            cta_text = cta_mapping.get(top_label, "Menurut kamu gimana? Komen di bawah!")
            logger.info(f"✅ Smart CTA dihasilkan: '{cta_text}' (Kategori: {top_label})")
            return cta_text

        except Exception as e:
            logger.error(f"❌ Smart CTA gagal: {e}")
            return "Drop komentar kalian di bawah!"

ai_engine = AIEngine()
