import os
import json
import glob
from logger import logger
from datasets import load_dataset

class DatasetPreparer:
    def __init__(self, data_dir="modulTrain", min_files=100):
        self.data_dir = data_dir
        self.min_files = min_files
        self.jsonl_output = os.path.join(self.data_dir, "combined_dataset.jsonl")

    def combine_to_jsonl(self):
        """Menggabungkan semua file JSON di modulTrain menjadi satu file JSONL untuk fine-tuning"""
        logger.info("🔄 Memulai penggabungan dataset ke format JSONL...")
        json_files = glob.glob(os.path.join(self.data_dir, "*.json"))

        if not json_files:
            logger.warning("⚠️ Tidak ada file JSON untuk digabungkan.")
            return False

        try:
            with open(self.jsonl_output, "w", encoding="utf-8") as outfile:
                for f_path in json_files:
                    try:
                        with open(f_path, "r", encoding="utf-8") as infile:
                            data = json.load(infile)
                            # Tulis sebagai satu baris JSON
                            json.dump(data, outfile, ensure_ascii=False)
                            outfile.write("\n")
                    except Exception as parse_err:
                        logger.error(f"⚠️ Melewati file rusak {f_path}: {parse_err}")
                        continue

            logger.info(f"✅ Berhasil menggabungkan {len(json_files)} file menjadi {self.jsonl_output}")
            return True
        except Exception as e:
            logger.error(f"❌ Gagal menggabungkan JSON ke JSONL: {e}")
            return False

    def check_and_fallback(self):
        """Mengecek jumlah file JSON, jika kurang dari min_files, unduh dataset fallback dari Hugging Face"""
        json_files = glob.glob(os.path.join(self.data_dir, "*.json"))
        file_count = len(json_files)

        logger.info(f"📊 Pengecekan dataset: {file_count}/{self.min_files} file tersedia.")

        if file_count < self.min_files:
            logger.warning(f"⚠️ Dataset kurang dari {self.min_files}. Mengunduh fallback 'yahma/alpaca-cleaned' dari Hugging Face...")
            self._download_fallback_dataset()
        else:
            logger.info("✅ Dataset lokal sudah mencukupi.")

        # Gabungkan setelah dicek
        self.combine_to_jsonl()

    def _download_fallback_dataset(self):
        try:
            # Ambil 100 baris pertama dari dataset yahma/alpaca-cleaned untuk melengkapi kekurangan
            dataset = load_dataset("yahma/alpaca-cleaned", split="train[:100]")

            for i, item in enumerate(dataset):
                # Konversi format Alpaca ke format kita
                entry = {
                    "instruction": item.get("instruction", ""),
                    "input": item.get("input", ""),
                    "output": item.get("output", ""),
                    "metadata": {
                        "source": "yahma/alpaca-cleaned",
                        "fallback": True
                    }
                }

                # Simpan ke modulTrain
                file_path = os.path.join(self.data_dir, f"fallback_{i}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(entry, f, indent=4, ensure_ascii=False)

            logger.info("✅ Fallback dataset berhasil diunduh dan disimpan.")

        except ImportError:
            logger.error("❌ Modul 'datasets' belum terinstal. Jalankan 'pip install datasets' untuk menggunakan fallback.")
        except Exception as e:
            logger.error(f"❌ Gagal mengunduh dataset fallback: {e}")

dataset_prep = DatasetPreparer()
