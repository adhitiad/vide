import os
import time
from instagrapi import Client
from logger import logger

# ==============================================================================
# ⚠️ PENTING UNTUK USER ⚠️
# Anda WAJIB mengatur Env Vars `IG_USERNAME` dan `IG_PASSWORD`
# Sesi login akan disimpan di `ig_session.json` agar tidak diblokir Instagram.
# ==============================================================================

class InstagramUploader:
    def __init__(self):
        self.cl = Client()
        self.session_file = "ig_session.json"
        self.is_authenticated = False
        self._authenticate()

    def _authenticate(self):
        username = os.getenv("IG_USERNAME")
        password = os.getenv("IG_PASSWORD")

        if not username or not password:
            logger.warning("⚠️ Kredensial IG (IG_USERNAME/IG_PASSWORD) kosong. Auto-Upload IG Reels Mati.")
            return

        try:
            # Login via session caching
            if os.path.exists(self.session_file):
                logger.info("🔄 Membuka sesi Instagram lama...")
                self.cl.load_settings(self.session_file)
                self.cl.login(username, password)
                self.cl.get_timeline_feed() # Cek sesi masih valid
            else:
                logger.info("🔐 Meminta autentikasi Instagram baru...")
                # Beri jeda kecil agar request tidak dicurigai
                time.sleep(2)
                self.cl.login(username, password)
                self.cl.dump_settings(self.session_file)

            self.is_authenticated = True
            logger.info(f"✅ Terautentikasi Instagram sebagai @{username}.")
        except Exception as e:
            logger.error(f"❌ Autentikasi Instagram Gagal: {e}")
            # Hapus sesi usang jika login ditolak
            if "login_required" in str(e).lower() and os.path.exists(self.session_file):
                os.remove(self.session_file)
            self.is_authenticated = False

    def upload_to_reels(self, video_path: str, caption: str) -> str:
        """Mengunggah video ke IG Reels via API Privat Instagrapi"""
        if not self.is_authenticated:
            logger.warning("⚠️ IG Uploader tidak aktif. Lewati proses Reels.")
            return None

        if not os.path.exists(video_path):
            logger.error(f"❌ Video Reels tidak ditemukan: {video_path}")
            return None

        # Instagrapi butuh video rasio tertentu, editor.py kita sudah 9:16 (720x1280)
        logger.info("📤 Memulai Upload IG Reels...")
        try:
            # Upload clip to reels
            media = self.cl.clip_upload(
                video_path,
                caption,
                extra_data={
                    "custom_accessibility_caption": "AI Generated Opini Video",
                    "like_and_view_counts_disabled": 0,
                    "disable_comments": 0,
                }
            )

            # Mendapatkan tautan web
            if media and media.pk:
                ig_url = f"https://www.instagram.com/reel/{media.code}/"
                logger.info(f"🎉 Upload IG Reels BERHASIL! {ig_url}")
                return ig_url
            else:
                logger.error("❌ Reels Upload selesai tapi ID Media kosong.")
                return None

        except Exception as e:
            logger.error(f"❌ Instagram Reels Upload GAGAL: {e}")
            return None

ig_uploader = InstagramUploader()
