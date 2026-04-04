import os
import time
import json
import random
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    FeedbackRequired,
    LoginRequired,
    MediaError,
    ClientError,
)
from logger import logger
from typing import Optional


class InstagramUploader:
    def __init__(self):
        self.cl = Client()
        self.session_file = os.path.join("data", "ig_session.json")
        os.makedirs("data", exist_ok=True)
        self.username = os.getenv("IG_USERNAME")
        self.password = os.getenv("IG_PASSWORD")
        self.is_authenticated = False
        self.cl.request_timeout = 120  # 2 Menit timeout

    def _authenticate(self) -> bool:
        """
        Sistem Autentikasi dengan Session Caching & Challenge Detection.
        """
        if not self.username or not self.password:
            logger.error("❌ IG_USERNAME/PASSWORD kosong. Periksa file .env Anda!")
            return False

        try:
            # 1. Load Session
            if os.path.exists(self.session_file):
                logger.info("🔄 Memuat sesi Instagram lama...")
                try:
                    self.cl.load_settings(self.session_file)
                    self.cl.login(self.username, self.password)
                    # Test session
                    self.cl.get_timeline_feed()
                    logger.info(f"✅ Sesi VALID. Login sebagai @{self.username}")
                    self.is_authenticated = True
                    return True
                except LoginRequired:
                    logger.warning("⚠️ Sesi login kadaluarsa, mencoba re-login...")
                    if os.path.exists(self.session_file):
                        os.remove(self.session_file)
                except Exception as e:
                    logger.warning(f"⚠️ Sesi corrupt: {e}")
                    if os.path.exists(self.session_file):
                        os.remove(self.session_file)

            # 2. Fresh Login
            logger.info(f"🔐 Login baru ke Instagram: @{self.username}")
            time.sleep(random.uniform(2, 5))

            if self.cl.login(self.username, self.password):
                self.cl.dump_settings(self.session_file)
                logger.info("✅ Login berhasil & Sesi baru disimpan.")
                self.is_authenticated = True
                return True

            return False

        except ChallengeRequired:
            logger.error(
                "🛡️ Instagram CHALLENGE! Buka aplikasi IG di HP Anda untuk verifikasi."
            )
            return False
        except FeedbackRequired:
            logger.error(
                "🛑 Instagram FEEDBACK REQUIRED! Akun Anda dibatasi sementara."
            )
            return False
        except Exception as e:
            logger.error(f"❌ Error Auth Instagram: {e}")
            return False

    def upload_to_ig_reels(
        self, video_path: str, caption: str, max_retries: int = 2
    ) -> Optional[str]:
        """
        Refined Upload dengan retry dan penanganan media error.
        """
        if not os.path.exists(video_path):
            return None

        # Re-auth check
        if not self.is_authenticated:
            if not self._authenticate():
                return None

        for attempt in range(1, max_retries + 1):
            logger.info(f"📤 Upload ke IG Reels (Mencoba {attempt}/{max_retries})...")
            try:
                # Menambahkan variasi delay
                time.sleep(random.uniform(3, 7))

                # Posting Reel
                media = self.cl.clip_upload(Path(video_path), caption=caption)

                if media and media.code:
                    url = f"https://www.instagram.com/reels/{media.code}/"
                    logger.info(f"✨ SUKSES! IG Reel Online: {url}")
                    return url

                logger.error("❌ Upload selesai tapi tidak ada ID media.")

            except (MediaError, ClientError) as e:
                logger.warning(f"⚠️ Media/Client Error pada percobaan {attempt}: {e}")
                if "login_required" in str(e).lower():
                    self.is_authenticated = False
                    self._authenticate()
            except Exception as e:
                logger.error(f"❌ Fatal Error IG Upload: {e}")

            if attempt < max_retries:
                time.sleep(10)

        return None


ig_uploader = InstagramUploader()
