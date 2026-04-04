import yt_dlp
import os
import uuid
import glob
import datetime
from logger import logger


class VideoDownloader:
    def __init__(self, download_dir="data/downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

    def search_and_download(self, topic: str, max_duration: int = 1200) -> str | None:
        """Mencari video UGC berdasarkan opini / podcast di Indonesia dan mengunduhnya"""
        logger.info(f"🔍 Mencari video sumber untuk UGC Opini terkait: '{topic}'...")

        video_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(self.download_dir, f"{video_id}.%(ext)s")

        # Track filepath yang benar-benar diunduh via hook
        downloaded_filepath: list[str] = []

        def post_hook(*args):
            # Hook khusus untuk post-processor (Merger/MoveFiles)
            d = args[-1]
            if d['status'] == 'finished' and d.get('postprocessor') in ['MoveFiles', 'Merger']:
                filepath = d.get('info_dict', {}).get('filepath')
                if filepath and os.path.exists(filepath):
                    downloaded_filepath.append(filepath)

        def duration_filter(info_dict):
            duration = info_dict.get('duration')
            try:
                if duration is not None:
                    dur_val = float(duration)
                    if dur_val <= 60 or dur_val > max_duration:
                        return f"Durasi tidak sesuai: {dur_val}s"
            except (ValueError, TypeError):
                pass
            return None  # None berarti video diterima / lolos filter

        # Deteksi ffmpeg dari imageio_ffmpeg (WAJIB untuk Windows/Enviroment terbatas)
        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            logger.info(f"✅ FFmpeg ditemukan via imageio-ffmpeg: {ffmpeg_path}")
        except Exception as e:
            logger.warning(f"⚠️ Gagal memuat imageio-ffmpeg: {e}. Menggunakan fallback 'ffmpeg'.")
            ffmpeg_path = "ffmpeg"

        # Deteksi Node.js sebagai JS runtime untuk yt-dlp agar format lengkap tersedia
        import shutil
        node_path = shutil.which("node")
        js_runtimes = f"nodejs:{node_path}" if node_path else None

        ydl_opts = {
            # Utamakan format mp4 lengkap, fallback ke webm
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'match_filter': duration_filter,
            'ffmpeg_location': ffmpeg_path,
            'quiet': False, # Ubah ke False untuk debugging jika terjadi error lagi
            'no_warnings': False,
            'extract_audio': False,
            'postprocessor_hooks': [post_hook],
            'merge_output_format': 'mp4',
        }

        # Tambahkan Node.js JS runtime jika tersedia (menghilangkan WARNING)
        if js_runtimes:
            ydl_opts['js_runtime'] = js_runtimes
            logger.info(f"✅ Node.js ditemukan di '{node_path}', JS runtime aktif.")
        else:
            logger.warning("⚠️ Node.js tidak ditemukan. Beberapa format YouTube mungkin hilang. Install Node.js untuk performa maksimal.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Membuang stop words agar hanya tersisa kata kunci yang relevan
                stopwords = {
                    "dan", "atau", "tetapi", "yang", "di", "ke", "dari", "pada", "dalam",
                    "untuk", "dengan", "ini", "itu", "karena", "sebab", "sehingga", "bahwa",
                    "adalah", "merupakan", "yaitu", "yakni", "akan", "telah", "sedang",
                    "sudah", "belum", "bisa", "dapat", "mampu", "harus", "wajib", "tidak",
                    "bukan", "jangan", "sangat", "paling", "sekali", "jika", "kalau",
                    "bila", "saat", "ketika", "setelah", "sebelum"
                }
                simplified_words = [w for w in topic.split() if w.lower() not in stopwords]
                simplified_topic = " ".join(simplified_words[:3])

                current_year = datetime.datetime.now().year
                search_query = f"ytsearch10:{simplified_topic} {current_year}"

                logger.info(f"📡 Mencari kata kunci: '{simplified_topic}'. Mengekstrak metadata dari 10 video (Viral Weighting)...")
                info = ydl.extract_info(search_query, download=False)

                entries = info.get('entries', []) if info else []
                valid_entries = [e for e in entries if e is not None]

                # Fallback ekstrim jika tidak ada kandidat
                if not valid_entries:
                    logger.warning("⚠️ Video UGC tidak ditemukan. Melakukan pencarian ekstrim...")
                    ekstrim_query = f"ytsearch10:{simplified_words[0]} viral indonesia"
                    info_ekstrim = ydl.extract_info(ekstrim_query, download=False)
                    entries_e = info_ekstrim.get('entries', []) if info_ekstrim else []
                    valid_entries = [e for e in entries_e if e is not None]

                if not valid_entries:
                    logger.error("❌ Video UGC tetap tidak ditemukan. Menggagalkan task.")
                    return None

                # Viral Weighting: urutkan berdasarkan views terbanyak
                def parse_views(v):
                    try:
                        return int(v) if v is not None else 0
                    except (ValueError, TypeError):
                        return 0

                valid_entries.sort(key=lambda x: parse_views(x.get('view_count')), reverse=True)
                best_video = valid_entries[0]
                video_url = best_video.get('webpage_url') or best_video.get('url')

                logger.info(f"🏆 Video terpilih: '{best_video.get('title')}' ({best_video.get('view_count')} views)")

                # Unduh kandidat terbaik
                ydl.download([video_url])

                # Metode 1: Cek via progress hook (paling akurat)
                if downloaded_filepath:
                    fpath = downloaded_filepath[-1]
                    logger.info(f"✅ Berhasil mengunduh video UGC: {fpath}")
                    return fpath

                # Metode 2: Cari semua file dengan video_id di folder download (glob fallback)
                all_files = glob.glob(os.path.join(self.download_dir, f"{video_id}.*"))
                
                # Prioritaskan file .mp4, lalu format video lainnya
                video_exts = {'.mp4', '.webm', '.mkv', '.mov', '.avi', '.flv', '.ts', '.m4v'}
                video_files = [f for f in all_files if os.path.splitext(f)[1].lower() in video_exts]
                video_files.sort(key=lambda x: x.lower().endswith('.mp4'), reverse=True)

                if video_files:
                    fpath = video_files[0]
                    logger.info(f"✅ Berhasil mengunduh video UGC (glob): {fpath}")
                    return fpath

                logger.error(f"❌ Gagal mendapatkan file video secara lokal. File ditemukan: {all_files}")
                return None

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"❌ yt-dlp Error mengunduh UGC '{topic}': {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Kesalahan tak terduga saat mengunduh: {e}")
            return None

    def cleanup(self, filepath: str):
        if not (filepath and os.path.exists(filepath)):
            return

        import time
        import gc

        # Paksa GC untuk melepaskan file handle (MoviePy/OS handle)
        gc.collect()

        max_retries = 3
        for i in range(max_retries):
            try:
                os.remove(filepath)
                logger.info(f"🗑️ Membersihkan file sumber: {filepath}")
                return
            except OSError as e:
                if i < max_retries - 1:
                    logger.warning(f"⏳ File '{filepath}' masih terkunci, mencoba kembali ({i+1}/{max_retries})...")
                    time.sleep(2)  # Beri waktu Windows untuk melepaskan handle
                else:
                    logger.error(f"❌ Gagal menghapus {filepath} setelah {max_retries} kali percobaan: {e}")


downloader = VideoDownloader()
