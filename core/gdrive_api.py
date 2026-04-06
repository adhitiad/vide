import os
import asyncio
import pickle
from typing import Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GDriveApi:
    def __init__(self):
        self.creds = None
        self.service = None

    def _authenticate(self):
        """Autentikasi ke Google Drive API secara lazy."""
        if self.service is not None:
            return

        token_path = "token.json"
        secret_path = "client_secret.json"

        if os.path.exists("token.pickle"):
            # Backward compatibility kalau sebelumnya pakai pickle
            try:
                with open("token.pickle", "rb") as token:
                    self.creds = pickle.load(token)
            except Exception as e:
                logger.error(f"Failed to load token.pickle: {e}")
                pass

        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
                self.creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token:
                token.write(self.creds.to_json())

        self.service = build("drive", "v3", credentials=self.creds)

    def _get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Membuat folder jika belum ada, atau mengambil ID folder yang sudah ada."""
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = (
            self.service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        items = results.get("files", [])

        if not items:
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if parent_id:
                folder_metadata["parents"] = [parent_id]

            folder = (
                self.service.files().create(body=folder_metadata, fields="id").execute()
            )
            return folder.get("id")
        else:
            return items[0].get("id")

    def _upload_file_sync(self, file_path: str, parent_id: str, mimetype: str) -> str:
        """Upload file ke Google Drive (Synchronous)."""
        file_name = os.path.basename(file_path)
        file_metadata = {"name": file_name, "parents": [parent_id]}

        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)

        file = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )

        # Buat agar link dapat diakses publik/siapa saja yang memiliki link
        self.service.permissions().create(
            fileId=file.get("id"), body={"type": "anyone", "role": "reader"}
        ).execute()

        # Kita kembalikan webViewLink yang akan dikirim via Telegram
        return file.get("webViewLink")

    async def upload_asset_async(
        self, video_path: str, meta_text_path: str, platform: str
    ) -> Dict[str, Any]:
        """
        Upload asinkron video dan file meta.txt ke sub-folder platform.
        Misalnya platform = 'yt' -> Upload ke /konten/yt/
        """
        return await asyncio.to_thread(
            self._upload_flow, video_path, meta_text_path, platform
        )

    def _upload_flow(
        self, video_path: str, meta_text_path: str, platform: str
    ) -> Dict[str, Any]:
        """Alur upload sinkron yang akan dijalan di threadpool asyncio."""
        try:
            self._authenticate()

            # 1. Cari / buat folder ROOT 'konten'
            konten_folder_id = self._get_or_create_folder("konten")
            # 2. Cari / buat sub folder platform (yt, ig, tt)
            platform_folder_id = self._get_or_create_folder(
                platform, parent_id=konten_folder_id
            )

            # 3. Upload Video
            video_link = self._upload_file_sync(
                video_path, platform_folder_id, "video/mp4"
            )

            # 4. Upload Meta Text
            meta_link = None
            if os.path.exists(meta_text_path):
                meta_link = self._upload_file_sync(
                    meta_text_path, platform_folder_id, "text/plain"
                )

            return {"success": True, "video_link": video_link, "meta_link": meta_link}
        except Exception as e:
            logger.error(f"Failed to upload to GDrive for {platform}: {str(e)}")
            return {"success": False, "error": str(e)}


gdrive_api = GDriveApi()
