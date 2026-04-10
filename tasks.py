import os
import time
import asyncio
import logging
import datetime
from celery_worker import celery_app
from core.gdrive_api import gdrive_api
from data.mongodb_client import db
from core.telegram_bot import send_telegram_notification
from core.whatsapp_bot import (
    send_whatsapp_notification,
    send_staff_delegation_notification,
    send_weekly_roi_report,
)
from core.ai_models import ai_engine
from core.editor import video_editor

logger = logging.getLogger(__name__)


def check_and_deduct_quota(owner_username: str) -> bool:
    """
    Mengecek apakah user masih memiliki kuota render.
    Mendukung perpanjangan bulan otomatis (Individual) & Bulk (Business).
    """
    user = db.users.find_one({"username": owner_username})
    if not user:
        return False

    sub_id = user.get("subscription_id")
    sub = db.subscriptions.find_one({"_id": sub_id})
    if not sub:
        return False

    now = datetime.datetime.utcnow()

    # Check Expiry
    if sub.get("expiry_date") < now:
        logger.warning(f"⚠️ Subscription {sub_id} expired for {owner_username}")
        return False

    # Logic Refresh Bulanan (Individual)
    if sub.get("is_monthly_refresh"):
        if now >= sub.get("next_reset_date", now):
            # Reset kuota bulanan
            db.subscriptions.update_one(
                {"_id": sub_id},
                {
                    "$set": {
                        "used_this_month": 0,
                        "next_reset_date": now + datetime.timedelta(days=30),
                    }
                },
            )
            sub["used_this_month"] = 0

        current_used = sub.get("used_this_month", 0)
        max_quota = sub.get("monthly_quota", 0) + sub.get("extra_videos_count", 0)
    else:
        # Logic Bulk (Business)
        current_used = sub.get("used_total", 0)
        max_quota = sub.get("total_bulk_quota", 0) + sub.get("extra_videos_count", 0)

    if current_used >= max_quota:
        logger.warning(
            f"❌ Kuota habis untuk {owner_username} ({current_used}/{max_quota})"
        )
        return False

    # Deduct Quota
    if sub.get("is_monthly_refresh"):
        db.subscriptions.update_one(
            {"_id": sub_id}, {"$inc": {"used_this_month": 1}}
        )
    else:
        db.subscriptions.update_one(
            {"_id": sub_id}, {"$inc": {"used_total": 1}}
        )

    return True


def run_async(coro):
    """Membantu menjalankan coroutine di konteks task synchronous Celery."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ==========================================
# 🎬 TASK 1: PIPELINE RL UTAMA (PER USER)
# ==========================================
@celery_app.task(bind=True, name="tasks.run_rl_pipeline")
def run_rl_pipeline(self, owner_username: str):
    """
    Menjalankan proses Gym/RL Environment dengan pengecekan kuota SaaS.
    """
    if not check_and_deduct_quota(owner_username):
        logger.error(f"Quota exceeded or sub invalid for {owner_username}.")
        return {"status": "quota_exceeded"}

    logger.info(f"Starting Autonomous RL Pipeline for {owner_username}...")
    try:
        from environment.clipper_env import ContentCreatorEnv

        env = ContentCreatorEnv(owner_username=owner_username)
        obs, info = env.reset()
        done = False

        while not done:
            action = 1
            obs, reward, done, truncated, info = env.step(action)
            if done or truncated:
                break

        logger.info(f"RL Pipeline Completed successfully for {owner_username}.")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in RL pipeline task for {owner_username}: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="tasks.process_video_from_go")
def process_video_from_go(self, owner_username: str, video_path: str, source_title: str):
    """
    Menangani video yang diunduh oleh Go Engine dan memprosesnya hingga distribusi.
    """
    logger.info(f"📥 Menerima setoran video dari Go Engine untuk {owner_username}: {source_title}")
    
    if not check_and_deduct_quota(owner_username):
        logger.error(f"Quota exceeded or sub invalid for {owner_username}.")
        return {"status": "quota_exceeded"}

    try:
        # 1. Edit Video (Default ke Format 0 / Hormozi)
        # Pastikan path video valid (Go mengirim path relatif ke root)
        if not os.path.exists(video_path):
            # Coba cari jika path relatif dikirim
            potential_path = os.path.join(os.getcwd(), video_path.replace("../", ""))
            if os.path.exists(potential_path):
                video_path = potential_path
            else:
                logger.error(f"Video path {video_path} tidak ditemukan!")
                return {"status": "error", "message": "file_not_found"}

        edit_result = video_editor.process_video(video_path, design_profile_idx=0)
        
        if not edit_result or "error" in edit_result:
            logger.error(f"Gagal proses video: {edit_result.get('error')}")
            return {"status": "error", "message": "edit_failed"}

        output_video_path = edit_result.get("output_path")
        transcript = edit_result.get("transcript", "")
        cta_used = edit_result.get("cta_used", "")

        # 2. ML Quality Control
        virality_score = ai_engine.predict_virality_score(source_title, transcript)
        score_pct = virality_score * 100
        
        if score_pct < 65.0:
            logger.warning(f"🗑️ [QC REJECT] Skor {score_pct:.1f}% terlalu rendah. Dibuang.")
            if os.path.exists(output_video_path): os.remove(output_video_path)
            if os.path.exists(video_path): os.remove(video_path)
            return {"status": "rejected", "score": score_pct}

        # 3. Persiapkan metadata untuk distribusi
        platforms = ["youtube", "instagram", "facebook", "tiktok"]
        meta_paths = []
        is_red_list = score_pct <= 75.0

        for plat in platforms:
            meta_content = f"Title: {source_title}\nPlatform: {plat}\nScore: {score_pct:.1f}%\nCTA: {cta_used}\n"
            meta_path = f"{output_video_path}_{plat}_meta.txt"
            with open(meta_path, "w", encoding="utf-8") as f:
                f.write(meta_content)
            meta_paths.append(meta_path)

        # 4. Distribusi
        distribute_and_notify.delay(
            video_path=str(output_video_path),
            meta_paths=meta_paths,
            title=source_title,
            comment=cta_used,
            platforms=platforms,
            owner_username=owner_username,
            is_red_list=is_red_list
        )

        # 5. Cleanup video asal dari Go
        if os.path.exists(video_path):
            os.remove(video_path)

        return {"status": "success", "score": score_pct}

    except Exception as e:
        logger.error(f"Error in Go-video processing: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


# ==========================================
# 📦 TASK 2: DISTRIBUSI & NOTIFIKASI
# ==========================================
@celery_app.task(bind=True, name="tasks.distribute_and_notify")
def distribute_and_notify(
    self,
    video_path: str,
    meta_paths: list,
    title: str,
    comment: str,
    platforms: list,
    owner_username: str,
    is_red_list: bool = False,
):
    logger.info(
        f"🚀 Distribusi Cerdas: 1 Video, {len(platforms)} Meta Files untuk {owner_username}..."
    )

    if not os.path.exists(video_path):
        logger.error(f"Video file {video_path} not found!")
        return {"status": "error", "message": "Video not found"}

    try:
        # 1. Upload ke Google Drive via Smart Routing
        upload_result = run_async(
            gdrive_api.distribute_assets_async(video_path, meta_paths, platforms)
        )

        if not upload_result.get("success"):
            error_msg = upload_result.get("error", "Unknown error")
            logger.error(f"Drive Upload failed: {error_msg}")
            raise self.retry(countdown=300, max_retries=3)

        v_link = upload_result.get("video_link")

        # 2. Simpan ke Database sebagai WAITING_UPLOAD
        for plat in platforms:
            db.published_videos.insert_one(
                {
                    "owner_username": owner_username,
                    "platform": plat,
                    "topic_name": title,
                    "gdrive_link": v_link,
                    "video_url": "",
                    "views": 0,
                    "likes": 0,
                    "comments": 0,
                    "performance_status": (
                        "ACTION_REQUIRED_RED" if is_red_list else "WAITING_UPLOAD"
                    ),
                    "created_at": datetime.datetime.utcnow(),
                }
            )

        logger.info("✅ Data WAITING_UPLOAD berhasil disimpan ke MongoDB.")

        # 3. Tentukan jadwal optimal
        hour_now = time.localtime().tm_hour
        if 8 <= hour_now < 12:
            suggested_time = "Siang (12:00 - 13:00)"
        elif 12 <= hour_now < 18:
            suggested_time = "Sore (17:00 - 18:00)"
        else:
            suggested_time = "Malam (19:30 - 21:00)"

        # 4. Kirim Telegram ke Owner
        run_async(
            send_telegram_notification(
                title=title,
                video_link=v_link,
                meta_link="Cek folder platform masing-masing di GDrive",
                comment=comment,
                suggested_time=suggested_time,
                platform="ALL PLATFORMS",
            )
        )

        # 5. Kirim WhatsApp ke Owner (Legacy)
        run_async(
            send_whatsapp_notification(
                title=title,
                video_link=v_link,
                platform="ALL PLATFORMS",
                suggested_time=suggested_time,
                comment=comment,
            )
        )

        # 6. ✨ SaaS: Staff Delegation via WhatsApp
        run_async(
            send_staff_delegation_notification(
                owner_username=owner_username,
                title=title,
                video_link=v_link,
                platform="ALL PLATFORMS",
                suggested_time=suggested_time,
            )
        )

        # 7. Auto Cleanup file lokal
        if os.path.exists(video_path):
            os.remove(video_path)

        for m_path in meta_paths:
            if os.path.exists(m_path):
                os.remove(m_path)

        logger.info("✅ Selesai! File lokal telah dibersihkan.")
        return {"status": "uploaded_and_cleaned", "video_link": v_link}

    except Exception as e:
        logger.error(f"Distribution task encountered an error: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


# ==========================================
# 🔄 TASK 3: MULTI-TENANT SCHEDULER
# ==========================================
@celery_app.task(name="tasks.run_all_active_pipelines")
def run_all_active_pipelines():
    """
    Celery Beat: Menjalankan pipeline RL untuk SEMUA user aktif yang langganannya valid.
    Ini menggantikan args kosong di beat_schedule lama.
    """
    now = datetime.datetime.utcnow()

    active_users = list(
        db.users.find(
            {
                "is_active": True,
                "$or": [
                    {"subscription_expiry": {"$gte": now}},
                    {"subscription_expiry": {"$exists": False}},
                ],
            }
        )
    )

    if not active_users:
        logger.info("📭 Tidak ada user aktif. Tidak ada pipeline yang dijadwalkan.")
        return {"status": "no_active_users"}

    scheduled_count = 0
    for user in active_users:
        username = user["username"]
        try:
            run_rl_pipeline.delay(owner_username=username)
            scheduled_count += 1
            logger.info(
                f"✅ Pipeline RL dijadwalkan untuk: {username}"
            )
        except Exception as e:
            logger.error(f"❌ Gagal menjadwalkan pipeline untuk {username}: {e}")

    logger.info(
        f"🚀 [MULTI-TENANT] {scheduled_count}/{len(active_users)} pipeline berhasil dijadwalkan."
    )
    return {"status": "scheduled", "count": scheduled_count}


# ==========================================
# 📡 TASK 4: TREND-JACKING RADAR
# ==========================================
@celery_app.task(name="tasks.run_trend_jacking_radar")
def run_trend_jacking_radar():
    """
    Celery Beat: Scan berita trending lalu trigger produksi instan jika cocok dengan niche user.
    Dijalankan setiap 6 jam oleh Celery Beat.
    """
    from core.trend_radar import match_trend_with_user_niche

    now = datetime.datetime.utcnow()
    eligible_users = list(
        db.users.find(
            {
                "is_active": True,
                "auto_trend_jacking": True,
                "$or": [
                    {"subscription_expiry": {"$gte": now}},
                    {"subscription_expiry": {"$exists": False}},
                ],
            }
        )
    )

    if not eligible_users:
        logger.info("📭 Tidak ada user dengan Trend-Jacking aktif.")
        return {"status": "no_eligible_users"}

    triggered_count = 0
    for user in eligible_users:
        username = user["username"]
        try:
            matched_trend = match_trend_with_user_niche(user["_id"])
            if matched_trend:
                logger.info(
                    f"🔥 [TREND-JACK] Tren cocok untuk {username}: '{matched_trend}'"
                )

                # Log ke database untuk audit
                db.trend_jacking_logs.insert_one(
                    {
                        "owner_username": username,
                        "trend_matched": matched_trend,
                        "triggered_at": datetime.datetime.utcnow(),
                        "status": "PIPELINE_TRIGGERED",
                    }
                )

                # Trigger pipeline produksi video
                run_rl_pipeline.delay(owner_username=username)
                triggered_count += 1
            else:
                logger.info(
                    f"🔍 [TREND-JACK] Tidak ada tren yang cocok untuk {username}."
                )
        except Exception as e:
            logger.error(f"❌ [TREND-JACK] Error untuk {username}: {e}")

    return {"status": "completed", "triggered": triggered_count}


# ==========================================
# 📊 TASK 5: WEEKLY ROI REPORT
# ==========================================
@celery_app.task(name="tasks.generate_weekly_roi_report")
def generate_weekly_roi_report():
    """
    Celery Beat: Menghasilkan dan mengirim laporan ROI mingguan ke setiap Owner aktif.
    Dijalankan setiap hari Minggu jam 09:00 WIB.
    """
    now = datetime.datetime.utcnow()
    week_ago = now - datetime.timedelta(days=7)

    active_owners = list(
        db.users.find(
            {
                "is_active": True,
                "role": "owner",
                "$or": [
                    {"subscription_expiry": {"$gte": now}},
                    {"subscription_expiry": {"$exists": False}},
                ],
            }
        )
    )

    if not active_owners:
        logger.info("📭 Tidak ada Owner aktif untuk Weekly Report.")
        return {"status": "no_owners"}

    reports_sent = 0
    for owner in active_owners:
        username = owner["username"]
        try:
            # Query video minggu ini
            videos_this_week = list(
                db.published_videos.find(
                    {
                        "owner_username": username,
                        "created_at": {"$gte": week_ago},
                    }
                )
            )

            total_views = sum(v.get("views", 0) for v in videos_this_week)
            total_videos = len(videos_this_week)
            blacklisted = sum(
                1
                for v in videos_this_week
                if v.get("performance_status") == "BLACKLISTED"
            )
            green_vids = [
                v
                for v in videos_this_week
                if v.get("performance_status")
                in ("GREEN_LIGHT", "GREEN_DARK", "WAITING_UPLOAD")
            ]
            green_count = len(green_vids)

            # Cari video terbaik
            best_video = max(
                videos_this_week, key=lambda v: v.get("views", 0), default=None
            )

            # Hitung rata-rata skor ML
            scores = [
                v.get("score_pct", 0) for v in videos_this_week if v.get("score_pct")
            ]
            avg_ml = sum(scores) / len(scores) if scores else 0.0

            report_data = {
                "total_views": total_views,
                "total_videos_rendered": total_videos,
                "best_video_title": (
                    best_video.get("topic_name", "N/A") if best_video else "N/A"
                ),
                "best_video_views": (
                    best_video.get("views", 0) if best_video else 0
                ),
                "avg_ml_score": avg_ml,
                "blacklisted_count": blacklisted,
                "green_count": green_count,
            }

            # Simpan ke DB untuk histori
            db.weekly_reports.insert_one(
                {
                    "owner_username": username,
                    "report_data": report_data,
                    "generated_at": datetime.datetime.utcnow(),
                }
            )

            # Kirim via WhatsApp
            run_async(send_weekly_roi_report(username, report_data))
            reports_sent += 1
            logger.info(f"✅ Weekly Report terkirim untuk {username}.")

        except Exception as e:
            logger.error(f"❌ Gagal generate Weekly Report untuk {username}: {e}")

    return {"status": "completed", "reports_sent": reports_sent}


# ==========================================
# 🧹 TASK 6: AUTO EXPIRE & CLEANUP
# ==========================================
@celery_app.task(name="tasks.auto_expire_subscriptions")
def auto_expire_subscriptions():
    """
    Celery Beat: Menonaktifkan akun yang langganannya sudah habis.
    Dijalankan setiap hari jam 00:01 WIB.
    """
    now = datetime.datetime.utcnow()

    expired_users = db.users.update_many(
        {
            "is_active": True,
            "subscription_expiry": {"$lt": now},
        },
        {"$set": {"is_active": False}},
    )

    if expired_users.modified_count > 0:
        logger.warning(
            f"⚠️ [AUTO-EXPIRE] {expired_users.modified_count} akun dinonaktifkan karena langganan habis."
        )
    else:
        logger.info("✅ [AUTO-EXPIRE] Tidak ada akun yang perlu dinonaktifkan.")

    return {"status": "completed", "expired_count": expired_users.modified_count}
