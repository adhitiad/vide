# 🏗️ Rencana Implementasi Arsitektur Hybrid: Go + Python

Proyek `ai-clipper-hub` akan bermigrasi ke arsitektur hybrid untuk meningkatkan performa konkurensi dan efisiensi memori.

## 🌉 Pembagian Tugas

### 1. Go Engine (The Mechanics)
- **Repo**: `f:\code\vide\go_engine`
- **Tugas**:
    - **Web Scraping**: Mencari konten viral di YouTube, TikTok, dan Instagram (lebih cepat & paralel).
    - **Concurrent Downloader**: Mengunduh banyak file video secara paralel menggunakan Goroutines.
    - **Social API Gatekeeper**: Menangani interaksi dengan API platform sosial.
    - **Traffic Controller**: Mendorong tugas AI ke antrean Redis (Celery).

### 2. Python Core (The Brain)
- **Repo**: `f:\code\vide` (Root)
- **Tugas**:
    - **AI Video Analysis**: Menjalankan model Whisper (Transkripsi) dan PyTorch/TensorFlow untuk highlight video.
    - **Video Rendering**: Memotong video menggunakan FFmpeg (bisa melalui Rust extension yang sudah ada).
    - **Database Logic**: Menangani logika MongoDB dan manajemen user (SaaS).

## 📡 Mekanisme Komunikasi: Message Broker (Redis)

Kami menggunakan **Redis** sebagai jembatan. Go akan bertindak sebagai "Producer" yang mengirimkan tugas, dan Python Celery Worker akan bertindak sebagai "Consumer".

## 🛠️ Langkah-langkah Berikutnya
1. [ ] Selesaikan integrasi Redis di Go.
2. [ ] Pindahkan logika Scraping YouTube dari Python ke Go.
3. [ ] Implementasikan Parallel Downloader di Go untuk menghemat penggunaan RAM server saat mengunduh video besar.
4. [ ] Hubungkan Dashboard (main.py) untuk bisa memicu Go Engine.
