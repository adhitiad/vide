import yt_dlp
import os
import uuid
import glob
from logger import logger

class VideoDownloader:
    def __init__(self, download_dir="data/downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

    def search_and_download(self, topic: str, max_duration: int = 1200) -> str:
        """Mencari video berdasarkan topik dan mengunduhnya"""
        logger.info(f"🔍 Mencari video untuk topik: '{topic}'...")

        # Buat ID unik untuk output file
        video_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(self.download_dir, f"{video_id}.%(ext)s")

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'match_filter': yt_dlp.utils.match_filter_func("duration <= " + str(max_duration)),
            'quiet': True,
            'no_warnings': True,
            'extract_audio': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Cari 1 hasil teratas menggunakan 'ytsearch1'
                search_query = f"ytsearch1:{topic} podcast indonesia"
                info = ydl.extract_info(search_query, download=True)

                # Temukan file hasil unduhan
                downloaded_file = glob.glob(os.path.join(self.download_dir, f"{video_id}.*"))

                if downloaded_file:
                     logger.info(f"✅ Berhasil mengunduh video: {downloaded_file[0]}")
                     return downloaded_file[0]
                else:
                     logger.error(f"❌ Video tidak ditemukan untuk query: '{topic}'")
                     return None

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"❌ yt-dlp Error mengunduh '{topic}': {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Kesalahan tak terduga saat mengunduh: {e}")
            return None

    def cleanup(self, filepath: str):
        """Menghapus file video yang sudah diproses"""
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info(f"🗑️ Membersihkan file: {filepath}")
            except OSError as e:
                logger.warning(f"⚠️ Gagal menghapus {filepath}: {e}")

downloader = VideoDownloader()
