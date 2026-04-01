import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from logger import logger

# ==============================================================================
# ⚠️ PENTING UNTUK USER ⚠️
# Anda WAJIB menaruh file `client_secrets.json` dari Google Cloud Console
# di root folder `ai-clip-hub/` agar fitur auto-upload ke YouTube ini berfungsi.
# ==============================================================================

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

class YouTubeUploader:
    def __init__(self):
        self.credentials = None
        self.youtube = None
        self.is_authenticated = False
        self._authenticate()

    def _authenticate(self):
        """Autentikasi ke YouTube API menggunakan OAuth 2.0"""
        try:
            # Token pickle menyimpan kredensial akses dan refresh token
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    self.credentials = pickle.load(token)

            # Jika tidak ada kredensial yang valid, minta user login
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("🔄 Refreshing expired YouTube token...")
                    self.credentials.refresh(Request())
                else:
                    if not os.path.exists('client_secrets.json'):
                        logger.warning("⚠️ File 'client_secrets.json' tidak ditemukan. Fitur Auto-Upload dinonaktifkan.")
                        return

                    logger.info("🔐 Meminta autentikasi YouTube pertama kali. Silakan login di browser.")
                    # Jika dijalankan via docker/server tanpa GUI, flow ini mungkin terblokir.
                    # Perlu local server untuk callback.
                    flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
                    self.credentials = flow.run_local_server(port=0)

                # Simpan kredensial untuk iterasi berikutnya
                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.credentials, token)

            self.youtube = build('youtube', 'v3', credentials=self.credentials)
            self.is_authenticated = True
            logger.info("✅ Berhasil terautentikasi dengan YouTube API.")

        except Exception as e:
            logger.error(f"❌ Gagal autentikasi YouTube API: {e}")
            self.is_authenticated = False

    def upload_to_youtube_shorts(self, video_path: str, title: str, description: str, tags: list = None, privacy_status: str = "public") -> str:
        """
        Mengunggah video ke YouTube Shorts.
        :param video_path: Path lokal file video (.mp4)
        :param title: Judul video (akan otomatis ditambahkan #Shorts jika belum ada)
        :param description: Deskripsi / Transkrip video
        :param tags: Daftar tag
        :param privacy_status: 'public', 'private', atau 'unlisted'
        :return: URL video YouTube atau None jika gagal
        """
        if not self.is_authenticated or not self.youtube:
            logger.warning("⚠️ Uploader tidak terautentikasi. Video tidak diunggah ke YouTube.")
            return None

        if not os.path.exists(video_path):
            logger.error(f"❌ File video tidak ditemukan: {video_path}")
            return None

        # Pastikan judul mengandung #Shorts
        if "#Shorts" not in title and "#shorts" not in title:
             title = f"{title[:80]} #Shorts" # Batasi panjang judul agar tidak melebihi 100 karakter

        if tags is None:
            tags = ["Shorts", "Viral", "Trending", "Indonesia"]
        elif "Shorts" not in tags:
            tags.append("Shorts")

        logger.info(f"📤 Memulai upload YouTube Shorts: '{title}' ({privacy_status})")

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '22' # 22 = People & Blogs, 27 = Education
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }

        try:
            # Upload video secara bertahap (resumable)
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')

            request = self.youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media
            )

            # Eksekusi request upload
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"⏳ Upload progress: {int(status.progress() * 100)}%")

            video_id = response.get('id')
            if video_id:
                youtube_url = f"https://www.youtube.com/shorts/{video_id}"
                logger.info(f"🎉 Upload BERHASIL! URL: {youtube_url}")
                return youtube_url
            else:
                logger.error("❌ Upload selesai tapi tidak mendapatkan Video ID.")
                return None

        except Exception as e:
            logger.error(f"❌ YouTube Upload GAGAL (API Error/Quota Limit): {e}")
            return None

youtube_uploader = YouTubeUploader()
