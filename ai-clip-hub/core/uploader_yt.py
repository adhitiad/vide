import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from logger import logger

SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.force-ssl']

class YouTubeUploader:
    def __init__(self):
        self.credentials = None
        self.youtube = None
        self.is_authenticated = False
        self._authenticate()

    def _authenticate(self):
        try:
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    self.credentials = pickle.load(token)

            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("🔄 Refreshing expired YouTube token...")
                    self.credentials.refresh(Request())
                else:
                    if not os.path.exists('client_secrets.json'):
                        logger.warning("⚠️ File 'client_secrets.json' tidak ditemukan. Auto-Upload YT Mati.")
                        return

                    logger.info("🔐 Meminta autentikasi YouTube. Login di browser...")
                    flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
                    self.credentials = flow.run_local_server(port=0)

                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.credentials, token)

            self.youtube = build('youtube', 'v3', credentials=self.credentials)
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
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment_text
                        }
                    }
                }
            }
            response = self.youtube.commentThreads().insert(
                part="snippet",
                body=comment_body
            ).execute()

            logger.info("📌 Komentar Pancingan Berhasil Di-Pin!")
        except Exception as e:
            logger.error(f"❌ Gagal menyematkan komentar YouTube: {e}")

    def upload_to_youtube_shorts(self, video_path: str, title: str, description: str, tags: list = None, privacy_status: str = "public", comment_text: str = "") -> str:
        if not self.is_authenticated or not self.youtube:
            return None

        if not os.path.exists(video_path):
            return None

        if "#Shorts" not in title and "#shorts" not in title:
             title = f"{title[:80]} #Shorts"

        if tags is None: tags = ["Shorts", "Viral"]

        logger.info(f"📤 Uploading YT Shorts: '{title}'")

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }

        try:
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
            request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status: logger.info(f"⏳ Upload progress: {int(status.progress() * 100)}%")

            video_id = response.get('id')
            if video_id:
                youtube_url = f"https://www.youtube.com/shorts/{video_id}"
                logger.info(f"🎉 Upload YouTube BERHASIL! {youtube_url}")

                # UGC Engagement Hack: Pin Komentar
                if comment_text:
                    self._pin_first_comment(video_id, comment_text)

                return youtube_url
            else:
                return None
        except Exception as e:
            logger.error(f"❌ YouTube Upload Gagal: {e}")
            return None

youtube_uploader = YouTubeUploader()
