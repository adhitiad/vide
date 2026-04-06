import os
import aiohttp
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def send_telegram_notification(title: str, video_link: str, meta_link: str, comment: str, suggested_time: str, platform: str):
    """
    Mengirim notifikasi Telegram asinkron kepada user berisi instruksi Upload Manual.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram Bot Token atau Chat ID tidak dikonfigurasi. Melewati notifikasi ke Telegram.")
        return

    # Buat pesan format HTML yang rapi
    message = (
        f"🚀 <b>AI-CLIP-HUB : Video Siap Upload!</b>\n\n"
        f"<b>Platform Target:</b> {platform.upper()}\n"
        f"<b>Judul Konten:</b> {title}\n"
        f"<b>Rekomendasi Waktu Upload:</b> {suggested_time}\n\n"
        f"📁 <b>Google Drive Links:</b>\n"
        f"🎬 <a href='{video_link}'>Download Video</a>\n"
        f"📝 <a href='{meta_link}'>Download Detail Meta</a>\n\n"
        f"💬 <b>Komentar Provokatif (Copy-Paste untuk pinning):</b>\n"
        f"<code>{comment}</code>\n\n"
        f"<i>Silahkan upload secara manual berdasarkan panduan di atas!</i>"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Notifikasi Telegram untuk '{title}' berhasil dikirim.")
                else:
                    error_text = await response.text()
                    logger.error(f"Gagal mengirim notifikasi Telegram: {error_text}")
    except Exception as e:
        logger.error(f"Error saat menghubungi Telegram API: {str(e)}")
