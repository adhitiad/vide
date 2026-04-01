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

        # Inisialisasi IndoBERT untuk sentimen evaluasi (Simulasi Reward UGC)
        try:
            self.indobert_pipeline = pipeline(
                "sentiment-analysis",
                model="indobenchmark/indobert-base-p1",
                device=0 if self.device == "cuda" else -1
            )
            logger.info("✅ IndoBERT (indobenchmark) berhasil dimuat untuk Analisis Sentimen.")
        except Exception as e:
            logger.error(f"❌ Gagal memuat IndoBERT: {e}")
            self.indobert_pipeline = None

    def transcribe_audio(self, audio_path: str):
        if not self.whisper_model:
            logger.error("⚠️ Whisper tidak tersedia.")
            return []

        logger.info(f"🎙️ Memulai transkripsi: {audio_path}")
        try:
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
        if not self.mdeberta_pipeline:
            logger.warning("⚠️ mDeBERTa tidak tersedia. Menggunakan CTA default.")
            return "Komen pendapatmu di bawah!"

        if not transcript_text or len(transcript_text.strip()) < 10:
             return "Bagaimana menurutmu? Komen ya!"

        logger.info("🧠 Menganalisis teks untuk Smart CTA...")
        candidate_labels = ["bertanya pendapat", "mengundang debat", "meminta saran", "berbagi pengalaman", "menyatakan fakta mengejutkan"]

        try:
            text_to_analyze = transcript_text[-1000:] if len(transcript_text) > 1000 else transcript_text
            result = self.mdeberta_pipeline(text_to_analyze, candidate_labels)
            top_label = result['labels'][0]

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

    def evaluate_sentiment(self, texts: list):
        """Mengevaluasi sentimen teks UGC (misal simulasi komentar) menggunakan IndoBERT"""
        if not self.indobert_pipeline:
             return 0.0 # Neutral fallback

        logger.info("🧠 Menganalisis Sentimen Komentar (IndoBERT)...")
        score = 0.0
        try:
             # IndoBERT pipeline return LABEL_0 (negative), LABEL_1 (neutral), LABEL_2 (positive)
             # (Atau variasi lain tergantung model, tapi indobenchmark umumnya klasifikasi multi class)
             # Demi penyederhanaan pipeline default HF untuk sentimen:
             results = self.indobert_pipeline(texts)
             for res in results:
                  label = res['label'].lower()
                  # Mapping label secara umum
                  if 'positive' in label or '1' in label or '2' in label:
                      score += 2.0
                  elif 'negative' in label or '0' in label:
                      score -= 1.5
                  else:
                      score += 0.5 # Neutral
             avg_score = score / len(texts) if texts else 0.0
             logger.info(f"✅ Sentimen terukur. Rata-rata Skor Berbasis Sentimen: {avg_score:.2f}")
             return avg_score
        except Exception as e:
             logger.error(f"❌ Evaluasi sentimen gagal: {e}")
             return 0.0

ai_engine = AIEngine()
