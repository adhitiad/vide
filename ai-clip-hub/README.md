# 🎬 AI-Clip-Hub (Single Server Edition)

AI-Clip-Hub adalah sistem otonom cerdas berbasis kecerdasan buatan (AI) yang bertugas sebagai *Content Creator* secara penuh. Mulai dari meriset tren viral, mengunduh bahan video, mengedit menjadi Shorts/Reels (dengan subtitle ala Hormozi), hingga mempublikasikannya secara otomatis ke YouTube Shorts.

Semua proses diawasi dan dikendalikan melalui sebuah Web Dashboard *Real-Time*!

## ✨ Fitur Utama

1. **🕵️‍♂️ AI Researcher Otonom**: Memindai tren terbaru di Google News RSS (Niche: AI, Bisnis, Saham, Crypto) tanpa *hardcode* topik.
2. **✂️ Smart Video Editor**: Mengunduh video menggunakan `yt-dlp`, memotongnya menjadi format vertikal (9:16), dan menambahkan animasi teks *word-by-word* ala Alex Hormozi menggunakan Whisper.
3. **🧠 Smart CTA & Flash Hack**: Menggunakan model `mDeBERTa` untuk memahami konteks video dan menghasilkan kalimat penutup (*Call to Action*) yang memancing komentar, serta menyisipkan frame berkedip di detik terakhir untuk meningkatkan metrik *rewatch* (loop).
4. **📈 Reinforcement Learning (Gym)**: Agen AI mempelajari topik mana yang paling banyak menghasilkan interaksi dengan sistem *Epsilon-Greedy* (Eksplorasi tren baru vs Eksploitasi tren sukses).
5. **📤 Auto-Upload YouTube Shorts**: Publikasi langsung ke internet tanpa intervensi manusia, menggunakan Google API (OAuth 2.0).
6. **🌐 Real-Time Dashboard**: Memantau seluruh sistem (Logs, Leaderboard, Publikasi) secara *live* melalui WebSockets dan FastAPI.

---

## 🛠️ Prasyarat (Requirements)

Sebelum menginstal, pastikan komputer/server Anda telah memiliki:
- **Python 3.9+**
- **FFmpeg** (Wajib terinstal di sistem operasi Anda untuk `moviepy` dan `whisper`)
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: [Download FFmpeg](https://ffmpeg.org/download.html) dan tambahkan ke Environment Variables (PATH).
- **Redis Server** (Opsional tapi disarankan, sistem memiliki fallback ke SQLite jika Redis mati).

---

## 🚀 Panduan Instalasi (Step-by-Step)

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/ai-clip-hub.git
cd ai-clip-hub
```

### 2. Buat Virtual Environment (Sangat Disarankan)
Gunakan `virtualenv` atau `conda` untuk mengisolasi instalasi Anda.
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependensi
```bash
pip install -r requirements.txt
```

### 4. Setup Kredensial YouTube API (Wajib untuk Auto-Upload)
Sistem ini membutuhkan otorisasi untuk mengunggah video ke channel YouTube Anda.
1. Pergi ke [Google Cloud Console](https://console.cloud.google.com/).
2. Buat Project Baru dan aktifkan **YouTube Data API v3**.
3. Buka menu **Credentials** -> Create Credentials -> **OAuth client ID** (Pilih Application type: Desktop App).
4. Download file JSON kredensial tersebut.
5. Ganti nama file menjadi `client_secrets.json` dan letakkan **tepat di dalam folder root** `ai-clip-hub/`.
   *(Catatan: Saat pertama kali dijalankan, sistem akan membuka browser agar Anda bisa login ke akun Google. Setelah login, file `token.pickle` akan terbuat sehingga sistem bisa berjalan otomatis seterusnya tanpa perlu login ulang).*

---

## 🎮 Cara Menjalankan Sistem

Jalankan perintah berikut di terminal Anda:

```bash
python main.py
```

Setelah log sistem berjalan, buka browser Anda dan akses Web Dashboard melalui:
👉 **http://localhost:8000**

Sistem sekarang akan menjalankan **Worker Process** (Mencari tren, mengedit, upload) dan **API Process** (Dashboard) secara paralel tanpa henti!

---

## 📂 Struktur Direktori

```text
ai-clip-hub/
├── main.py                  # Entry point (Multiprocessing Worker & API)
├── api.py                   # Web Dashboard & WebSockets
├── logger.py                # Konfigurasi Logging Terpusat
├── requirements.txt         # Daftar Dependensi
├── client_secrets.json      # (Wajib Dibuat Sendiri) Kredensial YouTube API
├── token.pickle             # (Dibuat Otomatis) Sesi Autentikasi YouTube
├── utils/
│   ├── helper.py
│   └── dataset_prep.py      # Penggabung dataset & HF Fallback
├── data/
│   ├── database.py          # SQLite Engine
│   ├── models.py            # Skema Tabel (TopicMemory, PublishedVideo)
│   └── redis_client.py      # Redis Cache / Fallback SQLite
├── core/
│   ├── ai_models.py         # Whisper & mDeBERTa Engine
│   ├── downloader.py        # Modul yt-dlp
│   ├── editor.py            # MoviePy Engine (Hormozi, CTA, Flash)
│   ├── knowledge.py         # Ekstrak Dataset Fine-Tuning
│   ├── researcher.py        # RSS Google News Scanner
│   └── uploader.py          # YouTube Shorts OAuth Uploader
└── environment/
    └── clipper_env.py       # Custom Gymnasium (Reinforcement Learning)
```

---

## 📝 Catatan Penting
- Karena memproses video dan menjalankan model AI (Whisper & mDeBERTa) secara lokal, disarankan menggunakan komputer dengan spesifikasi CPU yang cukup baik atau GPU pendukung (NVIDIA CUDA) agar proses render lebih cepat.
- Semua log akan disimpan ke dalam folder `logs/app.log` dan dapat dipantau langsung dari Dashboard.
- File dataset hasil ekstraksi agen AI akan disimpan di folder `modulTrain/` dalam format JSONL untuk kebutuhan Fine-Tuning *LLM* di masa mendatang.

Selamat membangun Kerajaan Konten Otonom! 🚀
