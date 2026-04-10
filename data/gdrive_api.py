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
        """Autentikasi ke Google Drive API secara lazy dengan perlindungan Headless/VPS."""
        if self.service is not None:
            return

        token_path = "token.json"
        secret_path = "client_secret.json"

        # Coba load token.pickle lama (Backward compatibility)
        if os.path.exists("token.pickle"):
            try:
                with open("token.pickle", "rb") as token:
                    self.creds = pickle.load(token)
            except Exception as e:
                logger.error(f"Failed to load token.pickle: {e}")

        # Coba load token.json standar
        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        # Jika token tidak valid atau tidak ada
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("🔄 Me-refresh token Google Drive...")
                self.creds.refresh(Request())
            else:
                # 🚨 PERBAIKAN FATAL: Mencegah sistem freeze di VPS (Server tanpa monitor)
                # Jika file client_secret.json tidak ada, lemparkan error jelas
                if not os.path.exists(secret_path):
                    raise FileNotFoundError(
                        f"File {secret_path} tidak ditemukan! Anda butuh kredensial OAuth."
                    )

                logger.warning("⚠️ Membuka browser untuk Autentikasi Google Drive...")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        secret_path, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                except Exception as e:
                    raise RuntimeError(
                        "Gagal membuka browser! Jika Anda menjalankan ini di VPS/Server, "
                        "jalankan script ini di Laptop Anda terlebih dahulu, lalu upload file 'token.json' "
                        "yang dihasilkan ke dalam folder VPS Anda."
                    ) from e

            # Simpan token baru
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
        return items[0].get("id")

    def _upload_file_sync(self, file_path: str, parent_id: str, mimetype: str) -> str:
        """Upload file ke Google Drive (Synchronous) dan set jadi Public Reader."""
        file_name = os.path.basename(file_path)
        file_metadata = {"name": file_name, "parents": [parent_id]}
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)

        file = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )

        # Set akses public read agar bisa dilihat/diunduh via Telegram
        self.service.permissions().create(
            fileId=file.get("id"), body={"type": "anyone", "role": "reader"}
        ).execute()

        return file.get("webViewLink")

    async def distribute_assets_async(
        self, video_path: str, meta_paths: list, platforms: list
    ) -> Dict[str, Any]:
        """
        SMART ROUTING UPLOAD:
        1. MP4 diupload HANYA SEKALI ke /konten/master_video/
        2. File Meta (.txt) diupload ke masing-masing folder platform (misal: /konten/yt/)
        """
        return await asyncio.to_thread(
            self._distribute_flow, video_path, meta_paths, platforms
        )

    def _distribute_flow(
        self, video_path: str, meta_paths: list, platforms: list
    ) -> Dict[str, Any]:
        try:
            self._authenticate()
            konten_folder_id = self._get_or_create_folder("konten")

            # 1. Upload Video Utama (Hanya 1x)
            logger.info(f"📤 Uploading Master Video: {os.path.basename(video_path)}")
            master_folder_id = self._get_or_create_folder(
                "master_video", parent_id=konten_folder_id
            )
            video_link = self._upload_file_sync(
                video_path, master_folder_id, "video/mp4"
            )

            # 2. Upload File Teks Meta ke Masing-masing Folder Platform
            meta_links = {}
            for plat, meta_path in zip(platforms, meta_paths):
                if os.path.exists(meta_path):
                    logger.info(
                        f"📝 Uploading Meta {plat.upper()}: {os.path.basename(meta_path)}"
                    )
                    plat_folder_id = self._get_or_create_folder(
                        plat, parent_id=konten_folder_id
                    )
                    link = self._upload_file_sync(
                        meta_path, plat_folder_id, "text/plain"
                    )
                    meta_links[plat] = link

            return {"success": True, "video_link": video_link, "meta_links": meta_links}

        except Exception as e:
            logger.error(f"❌ Failed to distribute assets to GDrive: {str(e)}")
            return {"success": False, "error": str(e)}


gdrive_api = GDriveApi()
