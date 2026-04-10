import os
import requests
import logging
import asyncio
from dotenv import load_dotenv
from data.mongodb_client import db

load_dotenv()
logger = logging.getLogger(__name__)

WA_TOKEN = os.getenv("WA_TOKEN")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
USER_PHONE_NUMBER = os.getenv("USER_PHONE_NUMBER")


async def _send_wa_message(to_phone: str, message_text: str):
    """
    Internal helper: mengirim satu pesan WhatsApp ke nomor tujuan via Meta Cloud API.
    """
    if not all([WA_TOKEN, WA_PHONE_NUMBER_ID]):
        logger.error("⚠️ Kredensial WhatsApp (WA_TOKEN / WA_PHONE_NUMBER_ID) belum diatur di .env!")
        return False

    url = f"https://graph.facebook.com/v18.0/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": True, "body": message_text},
    }

    try:
        response = await asyncio.to_thread(requests.post, url, headers=headers, json=data)
        if response.status_code == 200:
            logger.info(f"✅ WA terkirim ke {to_phone[-4:]}")
            return True
        else:
            logger.error(f"❌ Gagal kirim WA ke {to_phone[-4:]}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error saat mengirim WA: {str(e)}")
        return False


async def send_whatsapp_notification(
    title: str, video_link: str, platform: str, suggested_time: str, comment: str
):
    """
    Mengirim pesan notifikasi ke WhatsApp Owner (nomor default dari .env).
    Fungsi legacy: kompatibel dengan kode lama di tasks.py.
    """
    if not USER_PHONE_NUMBER:
        logger.error("⚠️ USER_PHONE_NUMBER belum diatur di .env!")
        return

    message_text = (
        f"🚨 *KONTEN {platform.upper()} SIAP!* 🚨\n\n"
        f"🎬 *Topik:* {title}\n"
        f"⏱️ *Saran Upload:* {suggested_time}\n\n"
        f"📁 *Link Master Video (GDrive):*\n{video_link}\n\n"
        f"📝 *Komentar Provokatif (Siap Copas):*\n_{comment}_\n\n"
        f"Cek folder GDrive platform masing-masing untuk file caption lengkap."
    )
    await _send_wa_message(USER_PHONE_NUMBER, message_text)


async def send_staff_delegation_notification(
    owner_username: str,
    title: str,
    video_link: str,
    platform: str,
    suggested_time: str,
):
    """
    SaaS Feature: WhatsApp Staff Delegation.
    Mengirim instruksi upload ke semua staf yang terdaftar di akun Owner.
    Jika tidak ada staf, notifikasi dikirim ke Owner langsung.
    """
    user = db.users.find_one({"username": owner_username})
    if not user:
        logger.error(f"❌ [WA DELEGATION] User '{owner_username}' tidak ditemukan di DB.")
        return

    staff_list = user.get("staff_delegation", [])
    owner_phone = user.get("no_hp_owner", USER_PHONE_NUMBER)

    # Format pesan instruksi untuk staf
    staff_message = (
        f"📋 *INSTRUKSI UPLOAD DARI BOSS* 📋\n\n"
        f"🎬 *Judul:* {title}\n"
        f"📱 *Platform:* {platform.upper()}\n"
        f"⏱️ *Jadwal Upload:* {suggested_time}\n\n"
        f"📁 *Link Download Video:*\n{video_link}\n\n"
        f"📝 *Langkah-langkah:*\n"
        f"1. Download video dari link di atas\n"
        f"2. Buka file _meta.txt di folder GDrive untuk caption & hashtag\n"
        f"3. Upload ke {platform.upper()} pada jam {suggested_time}\n"
        f"4. Setelah upload, laporkan URL konten ke dashboard\n\n"
        f"⚠️ _Deadline: HARI INI sebelum {suggested_time}_"
    )

    if staff_list:
        # Kirim ke setiap staf yang terdaftar
        logger.info(f"📤 [WA DELEGATION] Mengirim instruksi ke {len(staff_list)} staf milik {owner_username}...")
        for staff in staff_list:
            staff_phone = staff.get("phone_number")
            staff_name = staff.get("name", "Staf")
            if staff_phone:
                personalized_msg = f"Halo {staff_name}! 👋\n\n{staff_message}"
                await _send_wa_message(staff_phone, personalized_msg)
            else:
                logger.warning(f"⚠️ Staf '{staff_name}' tidak punya nomor HP. Dilewati.")
    else:
        # Jika tidak ada staf, kirim instruksi ke Owner langsung
        logger.info(f"📤 [WA DELEGATION] Tidak ada staf, mengirim langsung ke Owner {owner_username}...")
        if owner_phone:
            await _send_wa_message(owner_phone, f"📋 *REMINDER UPLOAD*\n\n{staff_message}")
        else:
            logger.warning(f"⚠️ Owner {owner_username} juga tidak punya nomor HP. Tidak bisa kirim WA.")


async def send_weekly_roi_report(owner_username: str, report_data: dict):
    """
    SaaS Feature: Mengirim Laporan ROI Mingguan via WhatsApp ke Owner.
    """
    user = db.users.find_one({"username": owner_username})
    if not user:
        return

    owner_phone = user.get("no_hp_owner", USER_PHONE_NUMBER)
    if not owner_phone:
        logger.warning(f"⚠️ Tidak bisa kirim ROI report WA untuk {owner_username}: No HP kosong.")
        return

    total_views = report_data.get("total_views", 0)
    total_videos = report_data.get("total_videos_rendered", 0)
    best_video = report_data.get("best_video_title", "N/A")
    best_views = report_data.get("best_video_views", 0)
    avg_score = report_data.get("avg_ml_score", 0.0)
    blacklisted = report_data.get("blacklisted_count", 0)
    green_count = report_data.get("green_count", 0)

    message = (
        f"📊 *LAPORAN MINGGUAN AI-CLIP-HUB* 📊\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Akun:* {owner_username}\n"
        f"📅 *Periode:* 7 Hari Terakhir\n\n"
        f"🎬 *Total Video Diproduksi:* {total_videos}\n"
        f"👁️ *Total Views:* {total_views:,}\n"
        f"📈 *Rata-rata Skor ML:* {avg_score:.1f}%\n\n"
        f"🏆 *Video Terbaik:*\n"
        f"   📌 {best_video}\n"
        f"   👁️ {best_views:,} views\n\n"
        f"✅ *Hijau (Aman):* {green_count} video\n"
        f"🗑️ *Blacklisted:* {blacklisted} video\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Laporan otomatis dari AI-Clip-Hub Engine._"
    )

    await _send_wa_message(owner_phone, message)
    logger.info(f"✅ Weekly ROI Report terkirim ke {owner_username}.")
