import os
from logger import logger
from core.uploader_yt import youtube_uploader
from core.uploader_ig import ig_uploader
from core.uploader_fb import fb_uploader
from core.uploader_tt import tiktok_uploader

class UploaderManager:
    """
    Unified Uploader Manager to abstract different platform upload logic.
    Provides a standardized interface for the scheduler.
    """

    def __init__(self):
        self.platforms = {
            "youtube": self._upload_youtube,
            "instagram": self._upload_instagram,
            "facebook": self._upload_facebook,
            "tiktok": self._upload_tiktok
        }

    def upload_video(self, platform: str, video_path: str, title: str, description: str) -> str:
        """
        Routes the upload to the correct platform uploader.
        """
        platform = platform.lower()
        if platform not in self.platforms:
            logger.error(f"❌ Platform tidak didukung: {platform}")
            return ""

        if not os.path.exists(video_path):
            logger.error(f"❌ File video tidak ditemukan: {video_path}")
            return ""

        try:
            logger.info(f"🔄 Mencoba jalur distribusi: {platform}")
            result = self.platforms[platform](video_path, title, description)
            
            if not result:
                logger.warning(f"⚠️  Gagal login atau aksi di {platform}. Melewati login dan melanjutkan ke tugas berikutnya...")
                return ""
            
            return result

        except Exception as e:
            logger.error(f"❌ Kesalahan fatal pada {platform}: {e}. Lewati login...")
            return ""

    def _upload_youtube(self, path, title, desc):
        # YouTube Official API
        # Title and description are separate in YT
        return youtube_uploader.upload_shorts(path, title, desc)

    def _upload_instagram(self, path, title, desc):
        # Instagram Unofficial (instagrapi)
        # Combined caption
        caption = f"{title}\n\n{desc}"
        return ig_uploader.upload_to_ig_reels(path, caption)

    def _upload_facebook(self, path, title, desc):
        # Facebook Unofficial (Playwright)
        caption = f"{title}\n\n{desc}"
        # We implementation with 3 retries inside
        return fb_uploader.upload_to_facebook(path, caption) if fb_uploader.upload_to_facebook(path, caption) else ""

    def _upload_tiktok(self, path, title, desc):
        # TikTok Unofficial (Playwright)
        caption = f"{title} {desc}"
        return tiktok_uploader.upload_to_tiktok(path, caption) if tiktok_uploader.upload_to_tiktok(path, caption) else ""

uploader_manager = UploaderManager()
