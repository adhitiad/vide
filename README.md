# 🎬 AI-Clip-Hub (Hybrid Edition: Hono + Python)

AI-Clip-Hub adalah sistem otonom cerdas berbasis AI yang bertugas sebagai *Content Creator* secara penuh. Mulai dari meriset tren viral, mengunduh bahan video, mengedit menjadi Shorts/Reels (dengan subtitle ala Hormozi), hingga mempublikasikannya secara otomatis.

Dalam versi **Unified Hybrid** ini, arsitektur dibagi menjadi dua entitas terpisah untuk performa optimal:
- **API Gateway & Dashboard (Hono/Bun)**: Menangani lalu-lintas jaringan, *WebSockets*, Autentikasi JWT, *API Docs (Swagger UI/Scalar)*, dan pendelegasian tugas ke MongoDB & Redis secara *Real-Time*.
- **Otot Komputasi AI (Python Celery Worker)**: Pekerja murni (*Headless Worker*) untuk mengeksekusi model AI (Whisper, mDeBERTa), pemotongan *FFmpeg* (`moviepy`), dan Algoritma **Reinforcement Learning**.

Semua proses tetap diawasi dan dikendalikan melalui sebuah Web Dashboard *Real-Time*!

## ✨ Fitur Utama

1. **🕵️‍♂️ AI Researcher Otonom**: Memindai tren terbaru (Niche: AI, Bisnis, Saham, Crypto) tanpa *hardcode* topik.
2. **✂️ Smart Video Editor**: Download video, potong vertikal (9:16), dan tambah animasi teks *word-by-word* pakai Whisper.
3. **🧠 Smart CTA & Flash Hack**: Memakai model `mDeBERTa` untuk menyisipkan ajakan *Call to Action* berdasarkan nuansa konten.
4. **📈 Reinforcement Learning (Gym)**: Agen AI eksplorasi topik viral mana yang harus dirender ulang (*Epsilon-Greedy*).
5. **🌐 Hono Dashboard & API Specs**: Terkoneksi ke MongoDB dan WebSockets secara instan, menyajikan performa I/O tinggi bebas *blocking*!

---

## 🛠️ Prasyarat (Requirements)

Sebelum menginstal, pastikan komputer/server Anda telah memiliki:
- **Bun** (Pengganti Node.js untuk I/O Engine Super Cepat). Instal: `powershell -c "irm bun.sh/install.ps1 | iex"` (di Windows)
- **Python 3.9+** & **Virtualenv**
- **MongoDB Server** (Terinstall lokal atau URL via `.env`)
- **Redis Server** (Wajib, sebagai urat nadi komunikasi antara Hono dan Celery Pekerja AI).
- **FFmpeg** (Wajib ada di PATH Windows)

---

## 🚀 Panduan Instalasi (Step-by-Step)

### 1. Ekstensi & Repository
Pastikan berada di folder hasil clone repositori utama.

### 2. Setup Python Worker (Celery AI)
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Setup Hono API Gateway
```bash
cd ts_engine
bun install
```

### 4. Setup Kredensial & Tokens
1. Duplikasi `.env.example` ke `.env` pada folder akar (root) lalu ganti URL Redis dan MongoDB Anda.
2. Ambil **OAuth Client ID** Google Cloud untuk Auto-Uploader jika menggunakan fitur YouTube API. (Simpan `client_secrets.json` dan `token.pickle` Anda ke root sesuai kebutuhan Uploader).

---

## 🎮 Cara Menjalankan Sistem

Anda cukup mengklik ganda satu script sakti:
👉 **`jalankan_semua.ps1`** (Disarankan, via PowerShell)
👉 **`jalankan_semua.bat`** (Via Command Prompt)

Skrip otomatis akan meluncurkan:
1. Terminal 1: Celery Worker untuk memutar otak mesin Python (*Standby Mode*).
2. Terminal 2: Hono Server API Gateway berputar di Port `8080`.

### 📖 Dokumentasi API (Swagger UI & Scalar)
Hono menghadirkan Auto-Documentation yang dapat diuji interaktif di peramban Anda! Masuk ke sini begitu sistem dijalankan:
🔗 **http://localhost:8080/swagger** 

Akses Dashboard Stats & UI Utama (jika disertakan):
👉 **http://localhost:8080**

---

## 📂 Struktur Direktori Hybrid

```text
ai-clip-hub/
├── jalankan_semua.ps1       # Magic Launcher (Celery + Hono)
├── .env                     # File Rahasia / Token
├── ts_engine/               # API GATEWAY (BUN + HONO) -- Otak Jaringan!
│   ├── src/api/             # Routes (Auth, Dashboard, System, WebSockets)
│   ├── src/queue/celery.ts  # Bridging (Hono menembak tugas Python via Redis)
│   └── package.json         
├── celery_worker.py         # Entry point Python Celery
├── tasks.py                 # Daftar pekerjaan Python (Dipanggil oleh Hono)
├── core/                    # Engine AI, FFmpeg, Downloader, Uploader
└── environment/             # Reinforcement Learning (Gym)
```

---

Selamat membangun Kerajaan Konten Otonom Berkinerja Tinggi! 🚀
