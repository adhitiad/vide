"""
utils/dataset_prep.py
======================
Script untuk mengekstrak data dari MongoDB menjadi dataset AI.
Hanya mengambil video dengan performa "VIRAL" dan "GOOD".
"""

import os
import pandas as pd
from data.mongodb_client import db
from logger import logger


def export_training_data(output_file="data/output/viral_dataset.csv"):
    logger.info("📦 Mengekstrak data pelatihan dari MongoDB...")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    try:
        # Ambil video yang terbukti sukses (Views tinggi)
        successful_videos = list(
            db.published_videos.find({"performance_status": {"$in": ["VIRAL", "GOOD"]}})
        )

        if not successful_videos:
            logger.warning("⚠️ Belum ada data video VIRAL/GOOD untuk di-training.")
            return None

        dataset = []
        for vid in successful_videos:
            # Kita menggabungkan topik dan views untuk melatih IndoBERT
            # agar bisa memprediksi teks mana yang akan menghasilkan views tinggi
            dataset.append(
                {
                    "platform": vid.get("platform", "unknown"),
                    "topic": vid.get("topic_name", ""),
                    "views": vid.get("views", 0),
                    "likes": vid.get("likes", 0),
                    "comments": vid.get("comments", 0),
                    # Asumsi Anda menyimpan 'caption' atau 'transcript' di DB saat render
                    "caption": vid.get(
                        "caption", f"Video viral tentang {vid.get('topic_name')}"
                    ),
                    "label": 1 if vid.get("performance_status") == "VIRAL" else 0,
                }
            )

        df = pd.DataFrame(dataset)
        df.to_csv(output_file, index=False)
        logger.info(
            f"✅ Dataset berhasil diekspor ke {output_file} ({len(df)} baris data)."
        )
        logger.info(
            "👉 Upload file ini ke Google Drive Anda untuk dibaca oleh Google Colab."
        )

        return output_file
    except Exception as e:
        logger.error(f"❌ Gagal mengekstrak dataset: {e}")
        return None


if __name__ == "__main__":
    export_training_data()
