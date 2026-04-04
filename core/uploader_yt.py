import os
import pickle
import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from logger import logger

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Error codes yang harus di-retry keesokan hari (jangan crash)
RETRYABLE_HTTP_CODES = {
    400,  # Bad Request (sering terjadi saat kuota habis atau format salah)
    403,  # Forbidden / quotaExceeded
    429,  # Too Many Requests
    500,  # Internal Server Error YouTube
    503,  # Service Unavailable
}

# Error codes yang FATAL (jangan di-retry, perbaiki konfigurasi dulu)
FATAL_HTTP_CODES = {
    401,  # Unauthorized - Token expired/invalid, perlu re-auth manual
}


class YouTubeUploader:
    def __init__(self):
        self.credentials = None
        self.youtube = None
        self.is_authenticated = False
        self._authenticate()

    def _authenticate(self):
        try:
            if os.path.exists("token.pickle"):
                with open("token.pickle", "rb") as token:
                    self.credentials = pickle.load(token)

            if not self.credentials or not self.credentials.valid:
                if (
                    self.credentials
                    and self.credentials.expired
                    and self.credentials.refresh_token
                ):
                    logger.info("🔄 Refreshing expired YouTube token...")
                    self.credentials.refresh(Request())
                else:
                    if not os.path.exists("client_secrets.json"):
                        logger.warning(
                            "⚠️ File 'client_secrets.json' tidak ditemukan. Auto-Upload YT Mati."
                        )
                        return

                    logger.info("🔐 Meminta autentikasi YouTube. Login di browser...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "client_secrets.json", SCOPES
                    )
                    self.credentials = flow.run_local_server(port=8000)

                with open("token.pickle", "wb") as token:
                    pickle.dump(self.credentials, token)

            self.youtube = build("youtube", "v3", credentials=self.credentials)
            self.is_authenticated = True
            logger.info("✅ Terautentikasi dengan YouTube API (Upload & Comments).")

        except Exception as e:
            logger.error(f"❌ Autentikasi YouTube API Gagal: {e}")
            self.is_authenticated = False

    def _pin_first_comment(self, video_id: str, comment_text: str):
        """Membuat komentar pertama sebagai pemancing perdebatan (UGC Hack)"""
        logger.info(f"💬 Menyematkan Komentar Pancingan ke Video {video_id}...")
        try:
            comment_body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {"snippet": {"textOriginal": comment_text}},
                }
            }
            response = (
                self.youtube.commentThreads()
                .insert(part="snippet", body=comment_body)
                .execute()
            )

            logger.info("📌 Komentar Pancingan Berhasil Di-Pin!")
        except HttpError as e:
            logger.error(f"❌ Gagal menyematkan komentar YouTube (HttpError {e.status_code}): {e.reason}")
        except Exception as e:
            logger.error(f"❌ Gagal menyematkan komentar YouTube: {e}")

    def _mark_queue_status(
        self,
        queue_id: int,
        status: str,
        error_msg: str = None,
        error_code: int = None,
        published_url: str = None,
    ):
        """
        Update status di tabel UploadQueue agar bot tidak mati saat error.
        Program TIDAK akan crash — error dicatat di DB dan di-retry besok.
        """
        try:
            from data.database import SessionLocal
            from data.models import UploadQueue

            session = SessionLocal()
            try:
                record = session.query(UploadQueue).filter(UploadQueue.id == queue_id).first()
                if not record:
                    return

                record.status = status
                record.last_error = error_msg
                record.error_code = error_code
                if published_url:
                    record.published_url = published_url
                    record.published_at = datetime.datetime.utcnow()
                if status == "failed":
                    record.retry_count = (record.retry_count or 0) + 1
                    # Jadwalkan retry besok jam 14:30 WIB (setelah quota reset)
                    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
                    record.next_retry_at = tomorrow.replace(hour=7, minute=30, second=0)
                    # Marking abandoned jika sudah melebihi batas retry
                    if record.retry_count >= record.max_retries:
                        record.status = "abandoned"
                        logger.warning(
                            f"🚫 [QUEUE] Video '{record.title[:40]}' diabaikan setelah {record.retry_count}x gagal."
                        )

                session.commit()
                logger.info(f"💾 [QUEUE] Status video ID={queue_id} diupdate → '{status}'")
            except Exception as db_err:
                logger.error(f"❌ [QUEUE] Gagal update status DB: {db_err}")
                session.rollback()
            finally:
                session.close()
        except ImportError:
            pass  # Jika database belum tersedia, cukup log saja

    def add_to_queue(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list = None,
        topic_name: str = "",
    ) -> int:
        """
        Tambahkan video ke antrian upload (UploadQueue) tanpa langsung mengupload.
        Bot akan upload saat jadwal prime time tiba.
        Returns: ID record di tabel UploadQueue (atau -1 jika gagal)
        """
        try:
            from data.database import SessionLocal
            from data.models import UploadQueue

            session = SessionLocal()
            try:
                tags_csv = ",".join(tags) if tags else ""
                record = UploadQueue(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=tags_csv,
                    topic_name=topic_name,
                    status="pending",
                )
                session.add(record)
                session.commit()
                logger.info(f"📥 [QUEUE] Video '{title[:50]}' masuk antrian (ID={record.id})")
                return record.id
            except Exception as e:
                logger.error(f"❌ [QUEUE] Gagal menambah ke antrian: {e}")
                session.rollback()
                return -1
            finally:
                session.close()
        except ImportError:
            return -1

    def upload_to_youtube_shorts(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list = None,
        privacy_status: str = "public",
        comment_text: str = "",
        queue_id: int = None,  # Opsional: ID dari UploadQueue untuk update status
    ) -> str:
        """
        Upload video ke YouTube Shorts.

        Error Handling Strategy:
        - HttpError 400/403/429 → Status DB berubah ke 'failed', program TIDAK crash
        - Bot akan retry keesokan harinya jam 14:30 WIB (setelah quota reset)
        - HttpError 401 (Unauthorized) → Log warning, butuh re-auth manual, TIDAK crash
        - Exception lain → Log error, TIDAK crash, return None

        Returns: URL YouTube Shorts jika berhasil, None jika gagal.
        """
        if not self.is_authenticated or not self.youtube:
            logger.warning("⚠️ YouTube tidak terautentikasi. Upload dilewati.")
            return None

        if not os.path.exists(video_path):
            logger.error(f"❌ File video tidak ditemukan: {video_path}")
            if queue_id:
                self._mark_queue_status(queue_id, "failed", f"File tidak ditemukan: {video_path}")
            return None

        if "Shorts" not in title and "#shorts" not in title.lower():
            title = f"{title[:80]} #Shorts"

        if tags is None:
            tags = ["Shorts", "Viral"]

        logger.info(f"📤 Uploading YT Shorts: '{title}'")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Update status ke 'uploading' agar tidak ke-trigger dua kali
        if queue_id:
            self._mark_queue_status(queue_id, "uploading")

        try:
            media = MediaFileUpload(
                video_path, chunksize=-1, resumable=True, mimetype="video/mp4"
            )
            request = self.youtube.videos().insert(
                part=",".join(body.keys()), body=body, media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"⏳ Upload progress: {int(status.progress() * 100)}%")

            video_id = response.get("id")
            if video_id:
                youtube_url = f"https://www.youtube.com/shorts/{video_id}"
                logger.info(f"🎉 Upload YouTube BERHASIL! {youtube_url}")

                # Update DB status → published
                if queue_id:
                    self._mark_queue_status(queue_id, "published", published_url=youtube_url)

                # UGC Engagement Hack: Pin Komentar
                if comment_text:
                    self._pin_first_comment(video_id, comment_text)

                return youtube_url
            else:
                logger.error("❌ YouTube tidak mengembalikan video_id. Upload gagal.")
                if queue_id:
                    self._mark_queue_status(queue_id, "failed", "YouTube tidak mengembalikan video_id")
                return None

        except HttpError as http_err:
            """
            Tangkap HttpError secara spesifik TANPA mematikan program.
            
            Contoh error umum:
            - 400: uploadLimitExceeded → Kuota harian habis, retry besok
            - 403: forbidden/quotaExceeded → Kuota API habis, retry besok  
            - 429: rateLimitExceeded → Terlalu sering request, retry besok
            - 401: authError → Token expired, perlu re-auth manual (jangan auto-retry)
            """
            error_code = http_err.status_code
            error_reason = http_err.reason if hasattr(http_err, 'reason') else str(http_err)

            if error_code in FATAL_HTTP_CODES:
                logger.error(
                    f"🔐 [FATAL] YouTube HttpError {error_code}: {error_reason}\n"
                    f"   ⚠️  Token kadaluarsa atau tidak valid. Jalankan ulang auth manual!\n"
                    f"   💡 Hapus 'token.pickle' lalu restart program."
                )
                if queue_id:
                    self._mark_queue_status(
                        queue_id, "failed",
                        f"FATAL - Perlu re-auth: {error_reason}",
                        error_code=error_code
                    )
            elif error_code in RETRYABLE_HTTP_CODES:
                logger.warning(
                    f"⚠️  [RETRY BESOK] YouTube HttpError {error_code}: {error_reason}\n"
                    f"   📅 Video masuk antrian 'failed'. Akan di-retry jam 14:30 WIB besok\n"
                    f"      (setelah quota API YouTube di-reset tengah malam waktu Pasifik)."
                )
                if queue_id:
                    self._mark_queue_status(
                        queue_id, "failed",
                        f"HttpError {error_code}: {error_reason}",
                        error_code=error_code
                    )
            else:
                logger.error(
                    f"❌ [HttpError] YouTube error {error_code}: {error_reason}"
                )
                if queue_id:
                    self._mark_queue_status(
                        queue_id, "failed",
                        f"HttpError {error_code}: {error_reason}",
                        error_code=error_code
                    )

            # TIDAK raise exception → program melanjutkan eksekusi normal
            return None

        except Exception as e:
            # Tangkap semua error lain TANPA crash
            logger.error(
                f"❌ YouTube Upload Gagal (Error Tidak Dikenal): {type(e).__name__}: {e}\n"
                f"   💡 Video akan dimasukkan ke status 'failed' dan di-retry besok."
            )
            if queue_id:
                self._mark_queue_status(
                    queue_id, "failed",
                    f"{type(e).__name__}: {str(e)}"
                )
            return None


youtube_uploader = YouTubeUploader()
