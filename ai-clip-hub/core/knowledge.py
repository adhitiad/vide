import json
import os
import uuid
import datetime
from logger import logger

class KnowledgeBase:
    def __init__(self, data_dir="modulTrain"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def extract_and_save(self, topic: str, video_data: dict, reward: float = 0.0):
        """Menyimpan hasil ekstraksi ke folder modulTrain/ sebagai dataset fine-tuning"""
        if not video_data or not video_data.get("transcript"):
            logger.warning("⚠️ Tidak ada data valid untuk diekstrak ke Knowledge Base.")
            return False

        try:
            # Format JSON sesuai instruksi (Instruksi -> Input -> Output)
            # Ini sangat berguna untuk fine-tuning LLM seperti Llama atau Mistral
            dataset_entry = {
                "instruction": f"Buatkan naskah video pendek (Shorts/Reels) yang menarik tentang topik '{topic}'.",
                "input": f"Gunakan gaya bahasa ini dan tambahkan CTA '{video_data.get('cta_used', '')}'.",
                "output": video_data.get("transcript", ""),
                "metadata": {
                    "topic": topic,
                    "simulated_reward": reward,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "duration_seconds": video_data.get("duration", 0)
                }
            }

            # Simpan ke file JSON individual
            file_id = f"data_{uuid.uuid4().hex[:8]}.json"
            file_path = os.path.join(self.data_dir, file_id)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(dataset_entry, f, indent=4, ensure_ascii=False)

            logger.info(f"🧠 Data berhasil diekstrak ke Knowledge Base: {file_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Gagal mengekstrak dan menyimpan data ke KB: {e}")
            return False

knowledge_base = KnowledgeBase()
