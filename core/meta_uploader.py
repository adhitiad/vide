import os
import time
import requests
from logger import logger
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class MetaUploader:
    """
    Official Meta Graph API Uploader for Instagram & Facebook Reels.
    Supports Resumable Upload (Direct Binary) from local disk.
    """

    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        self.ig_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.fb_page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.api_version = "v20.0" # Ganti jika perlu versi terbaru

    def _check_config(self, platform: str):
        if not self.access_token:
            logger.error("❌ META_ACCESS_TOKEN tidak ditemukan di .env")
            return False
        if platform == "instagram" and not self.ig_account_id:
            logger.error("❌ INSTAGRAM_ACCOUNT_ID tidak ditemukan di .env")
            return False
        if platform == "facebook" and not self.fb_page_id:
            logger.error("❌ FACEBOOK_PAGE_ID tidak ditemukan di .env")
            return False
        return True

    # --- INSTAGRAM REELS (RESUMABLE) ---
    def upload_to_instagram(self, video_path: str, caption: str) -> Optional[str]:
        if not self._check_config("instagram"):
            return None

        file_size = os.path.getsize(video_path)
        logger.info(f"📸 Memulai upload IG Reels (Resumable): {os.path.basename(video_path)}")

        try:
            # 1. Inisialisasi Sesi Upload
            init_url = f"https://graph.facebook.com/{self.api_version}/{self.ig_account_id}/media"
            init_params = {
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": caption,
                "access_token": self.access_token
            }
            init_res = requests.post(init_url, params=init_params).json()
            
            if "id" not in init_res:
                 logger.error(f"❌ Gagal inisialisasi IG: {init_res}")
                 return None
            
            container_id = init_res["id"]
            
            # 2. Upload Binary ke RUpload
            # Catatan: Endpoint rupload berbeda dengan graph
            upload_url = f"https://graph.facebook.com/{self.api_version}/{container_id}"
            
            headers = {
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream"
            }
            
            with open(video_path, "rb") as f:
                upload_res = requests.post(
                    f"https://rupload.facebook.com/video-upload/{self.api_version}/{container_id}",
                    data=f,
                    headers=headers
                )
            
            if upload_res.status_code != 200:
                logger.error(f"❌ Gagal upload binary IG: {upload_res.text}")
                return None

            # 3. Polling Status (Transcoding Meta)
            logger.info("⏳ Menunggu Meta memproses video IG...")
            for _ in range(15): # Cek selama ~2.5 menit
                time.sleep(10)
                status_url = f"https://graph.facebook.com/{self.api_version}/{container_id}"
                status_params = {"fields": "status_code", "access_token": self.access_token}
                status_res = requests.get(status_url, params=status_params).json()
                
                if status_res.get("status_code") == "FINISHED":
                    break
                elif status_res.get("status_code") == "ERROR":
                    logger.error(f"❌ Transcoding IG Gagal: {status_res}")
                    return None
            else:
                logger.warning("⚠️ Timeout: Video IG belum siap setelah 150 detik.")

            # 4. Publikasikan
            publish_url = f"https://graph.facebook.com/{self.api_version}/{self.ig_account_id}/media_publish"
            publish_params = {
                "creation_id": container_id,
                "access_token": self.access_token
            }
            publish_res = requests.post(publish_url, params=publish_params).json()
            
            if "id" in publish_res:
                media_id = publish_res["id"]
                ig_url = f"https://www.instagram.com/reels/{media_id}/" # URL asumsi (perlu konfirmasi field)
                logger.info(f"✅ IG Reels berhasil dipublish: {ig_url}")
                return ig_url
            else:
                logger.error(f"❌ Gagal publikasi IG: {publish_res}")
                return None

        except Exception as e:
            logger.error(f"❌ Kesalahan Meta IG: {e}")
            return None

    # --- FACEBOOK REELS (DIRECT) ---
    def upload_to_facebook(self, video_path: str, caption: str) -> Optional[str]:
        if not self._check_config("facebook"):
            return None

        file_size = os.path.getsize(video_path)
        logger.info(f"💙 Memulai upload FB Reels: {os.path.basename(video_path)}")

        try:
            # 1. Start Phase
            url = f"https://graph.facebook.com/{self.api_version}/{self.fb_page_id}/video_reels"
            params = {
                "upload_phase": "start",
                "access_token": self.access_token
            }
            res_start = requests.post(url, params=params).json()
            video_id = res_start.get("video_id")
            upload_url = res_start.get("upload_url")

            if not video_id or not upload_url:
                logger.error(f"❌ Gagal start FB upload: {res_start}")
                return None

            # 2. Binary Upload
            headers = {
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream"
            }
            with open(video_path, "rb") as f:
                res_upload = requests.post(upload_url, data=f, headers=headers)
            
            if res_upload.status_code != 200:
                logger.error(f"❌ Gagal upload binary FB: {res_upload.text}")
                return None

            # 3. Finish Phase (Publish)
            params_finish = {
                "upload_phase": "finish",
                "access_token": self.access_token,
                "video_id": video_id,
                "description": caption,
                "video_state": "PUBLISHED"
            }
            res_finish = requests.post(url, params=params_finish).json()
            
            if res_finish.get("success"):
                fb_url = f"https://www.facebook.com/reels/{video_id}"
                logger.info(f"✅ FB Reels berhasil dipublish: {fb_url}")
                return fb_url
            else:
                logger.error(f"❌ Gagal publikasi FB: {res_finish}")
                return None

        except Exception as e:
            logger.error(f"❌ Kesalahan Meta FB: {e}")
            return None

meta_uploader = MetaUploader()
