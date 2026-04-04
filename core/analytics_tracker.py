"""
core/analytics_tracker.py
==========================
Modul Auto-Analytics Tracker untuk ai-clipper-hub.

Fungsi utama:
  - update_youtube_stats()   → Tarik viewCount/likeCount/commentCount via YouTube Data API v3
  - update_instagram_stats() → Tarik statistik via Instagrapi media_info()
  - run_all_trackers()       → Entry point yang dipanggil oleh APScheduler setiap 23:30 WIB

Logika Evaluasi Performa:
  - PENDING  → Baru dipublish, belum 24 jam
  - GOOD     → views >= 100 setelah 24 jam
  - LOW_VIEWS → views < 100 setelah 24 jam (memicu Self-Correction & Pivot di RL)
  - VIRAL    → views >= 1000 setelah 24 jam (topik mendapat bonus score di Redis)

Semua operasi dibungkus try-except per-video agar satu kegagalan tidak menghentikan tracker lain.
"""

import os
import pickle
import datetime
from typing import Optional

from logger import logger
from data.mongodb_client import db
from data.models import PublishedVideo

# ──────────────────────────────────────────────────────────────────────────────
# Threshold Performa (Dapat diubah via ENV atau hardcode di sini)
# ──────────────────────────────────────────────────────────────────────────────
THRESHOLD_LOW_VIEWS = int(os.getenv("ANALYTICS_LOW_VIEWS_THRESHOLD", "100"))
THRESHOLD_VIRAL = int(os.getenv("ANALYTICS_VIRAL_THRESHOLD", "1000"))
EVALUATION_WINDOW_HOURS = float(os.getenv("ANALYTICS_EVAL_WINDOW_HOURS", "24"))

# Hanya ambil video yang dipublish dalam N hari terakhir (hemat quota API)
TRACKING_WINDOW_DAYS = int(os.getenv("ANALYTICS_TRACKING_WINDOW_DAYS", "7"))


def _evaluate_and_update_status(video: PublishedVideo) -> str:
    """
    Hitung performance_status berdasarkan views dan waktu publikasi.
    Return status string yang baru.
    """
    hours_elapsed = video.hours_since_published

    # Belum cukup 24 jam → jangan evaluasi dulu
    if hours_elapsed < EVALUATION_WINDOW_HOURS:
        return "PENDING"

    if video.views >= THRESHOLD_VIRAL:
        return "VIRAL"
    elif video.views >= THRESHOLD_LOW_VIEWS:
        return "GOOD"
    else:
        return "LOW_VIEWS"


def _get_youtube_client():
    """Buat YouTube API client dari token.pickle yang sudah ada."""
    try:
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        credentials = None
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                logger.info("🔄 [Analytics] Refreshing YouTube token...")
                credentials.refresh(Request())
                with open("token.pickle", "wb") as token:
                    pickle.dump(credentials, token)
            else:
                logger.error(
                    "❌ [Analytics] Token YouTube tidak valid. Jalankan auth ulang."
                )
                return None

        youtube = build("youtube", "v3", credentials=credentials)
        return youtube

    except Exception as e:
        logger.error(f"❌ [Analytics] Gagal membuat YouTube client: {e}")
        return None


def _get_ig_client():
    """Buat Instagrapi client dari ig_session.json yang sudah ada."""
    try:
        from instagrapi import Client

        username = os.getenv("IG_USERNAME")
        password = os.getenv("IG_PASSWORD")

        if not username or not password:
            logger.warning("⚠️ [Analytics] Kredensial IG tidak ada. Skip analytics IG.")
            return None

        cl = Client()
        session_file = "ig_session.json"

        if os.path.exists(session_file):
            cl.load_settings(session_file)
            cl.login(username, password)
        else:
            logger.warning(
                "⚠️ [Analytics] ig_session.json tidak ditemukan. Skip analytics IG."
            )
            return None

        return cl

    except Exception as e:
        logger.error(f"❌ [Analytics] Gagal membuat Instagram client: {e}")
        return None


def update_youtube_stats() -> dict:
    """
    Ambil statistik (viewCount, likeCount, commentCount) dari YouTube Data API v3
    untuk semua PublishedVideo platform='youtube' yang dipublish dalam 7 hari terakhir.

    Return:
        dict berisi ringkasan: {"updated": int, "failed": int, "low_views": int, "viral": int}
    """
    logger.info("📊 [Analytics YT] Memulai update statistik YouTube...")
    summary = {"updated": 0, "failed": 0, "low_views": 0, "viral": 0, "good": 0}

    youtube = _get_youtube_client()
    if not youtube:
        logger.error(
            "❌ [Analytics YT] Melewati update YT karena client tidak tersedia."
        )
        return summary

    try:
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(
            days=TRACKING_WINDOW_DAYS
        )
        videos_data = db.published_videos.find(
            {
                "platform": "youtube",
                "published_at": {"$gte": cutoff_date},
                "performance_status": {"$ne": "VIRAL"},
            }
        )

        videos = [PublishedVideo.from_dict(v) for v in videos_data]

        if not videos:
            logger.info(
                "ℹ️ [Analytics YT] Tidak ada video YouTube untuk ditracking dalam 7 hari."
            )
            return summary

        logger.info(f"📋 [Analytics YT] Memproses {len(videos)} video YouTube...")

        # Batch request per 50 video (limit YouTube Data API)
        batch_size = 50
        for i in range(0, len(videos), batch_size):
            batch = videos[i : i + batch_size]

            # Kumpulkan video ID dari platform_video_id atau ekstrak dari URL
            id_to_video = {}
            for v in batch:
                vid_id = _extract_youtube_id(v)
                if vid_id:
                    id_to_video[vid_id] = v
                else:
                    logger.warning(
                        f"⚠️ [Analytics YT] Tidak bisa ekstrak video ID dari: {v.video_url}"
                    )
                    summary["failed"] += 1

            if not id_to_video:
                continue

            video_ids_str = ",".join(id_to_video.keys())

            # Satu API call untuk seluruh batch (hemat quota)
            try:
                response = (
                    youtube.videos().list(part="statistics", id=video_ids_str).execute()
                )
            except Exception as api_err:
                logger.error(
                    f"❌ [Analytics YT] YouTube API error saat batch request: {api_err}\n"
                    f"   💡 Kemungkinan quota habis. Akan dicoba lagi besok."
                )
                summary["failed"] += len(id_to_video)
                continue

            items = response.get("items", [])
            returned_ids = {item["id"] for item in items}

            for item in items:
                vid_id = item["id"]
                stats = item.get("statistics", {})
                video = id_to_video.get(vid_id)
                if not video:
                    continue

                try:
                    video.views = int(stats.get("viewCount", 0))
                    video.likes = int(stats.get("likeCount", 0))
                    video.comments = int(stats.get("commentCount", 0))
                    video.last_checked = datetime.datetime.utcnow()

                    new_status = _evaluate_and_update_status(video)
                    old_status = video.performance_status

                    # Update di MongoDB
                    db.published_videos.update_one(
                        {"_id": video._id},
                        {
                            "$set": {
                                "views": video.views,
                                "likes": video.likes,
                                "comments": video.comments,
                                "last_checked": video.last_checked,
                                "performance_status": video.performance_status,
                            }
                        },
                    )

                    summary["updated"] += 1
                    if new_status == "LOW_VIEWS":
                        summary["low_views"] += 1
                    elif new_status == "VIRAL":
                        summary["viral"] += 1
                        _boost_viral_topic(video.topic_name)
                    elif new_status == "GOOD":
                        summary["good"] += 1

                except Exception as update_err:
                    logger.error(
                        f"❌ [Analytics YT] Gagal update video URL={video.video_url}: {update_err}"
                    )
                    summary["failed"] += 1

            # Tandai video yang tidak ada di respons API (mungkin dihapus/private)
            for missing_id in id_to_video:
                if missing_id not in returned_ids:
                    v = id_to_video[missing_id]
                    logger.warning(
                        f"⚠️ [Analytics YT] Video ID '{missing_id}' tidak ditemukan di API "
                        f"(mungkin terhapus/private). URL: {v.video_url}"
                    )
                    summary["failed"] += 1

        logger.info(
            f"✅ [Analytics YT] Selesai. "
            f"Updated={summary['updated']}, "
            f"LOW_VIEWS={summary['low_views']}, "
            f"VIRAL={summary['viral']}, "
            f"Gagal={summary['failed']}"
        )

    except Exception as e:
        logger.error(f"❌ [Analytics YT] Error fatal: {e}")

    return summary


def update_instagram_stats() -> dict:
    """
    Ambil statistik dari Instagram via Instagrapi media_info()
    untuk semua PublishedVideo platform='instagram' dalam 7 hari terakhir.

    Return:
        dict berisi ringkasan: {"updated": int, "failed": int, "low_views": int}
    """
    logger.info("📊 [Analytics IG] Memulai update statistik Instagram...")
    summary = {"updated": 0, "failed": 0, "low_views": 0, "viral": 0, "good": 0}

    ig_client = _get_ig_client()
    if not ig_client:
        logger.warning(
            "⚠️ [Analytics IG] Skip Instagram analytics (client tidak tersedia)."
        )
        return summary

    try:
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(
            days=TRACKING_WINDOW_DAYS
        )
        videos_data = db.published_videos.find(
            {
                "platform": "instagram",
                "published_at": {"$gte": cutoff_date},
                "performance_status": {"$ne": "VIRAL"},
            }
        )

        videos = [PublishedVideo.from_dict(v) for v in videos_data]

        if not videos:
            logger.info("ℹ️ [Analytics IG] Tidak ada video IG untuk ditracking.")
            return summary

        logger.info(f"📋 [Analytics IG] Memproses {len(videos)} video Instagram...")

        for video in videos:
            media_pk = _extract_ig_media_pk(video)
            if not media_pk:
                logger.warning(
                    f"⚠️ [Analytics IG] Tidak bisa ekstrak media PK dari: {video.video_url}"
                )
                summary["failed"] += 1
                continue

            try:
                # Instagrapi: media_info() mengembalikan object MediaV1
                media_info = ig_client.media_info(media_pk)

                # Ambil statistik (field name bisa bervariasi tergantung API response)
                video.views = (
                    getattr(media_info, "view_count", 0)
                    or getattr(media_info, "play_count", 0)
                    or 0
                )
                video.likes = getattr(media_info, "like_count", 0) or 0
                video.comments = getattr(media_info, "comment_count", 0) or 0
                video.last_checked = datetime.datetime.utcnow()

                # Update di MongoDB
                db.published_videos.update_one(
                    {"_id": video._id},
                    {
                        "$set": {
                            "views": video.views,
                            "likes": video.likes,
                            "comments": video.comments,
                            "last_checked": video.last_checked,
                            "performance_status": video.performance_status,
                        }
                    },
                )

                summary["updated"] += 1
                if new_status == "LOW_VIEWS":
                    summary["low_views"] += 1
                elif new_status == "VIRAL":
                    summary["viral"] += 1
                    _boost_viral_topic(video.topic_name)
                elif new_status == "GOOD":
                    summary["good"] += 1

            except Exception as media_err:
                logger.error(
                    f"❌ [Analytics IG] Gagal ambil info media '{media_pk}': {media_err}"
                )
                summary["failed"] += 1
                # Jangan stop loop, lanjutkan ke video berikutnya

        logger.info(
            f"✅ [Analytics IG] Selesai. "
            f"Updated={summary['updated']}, "
            f"LOW_VIEWS={summary['low_views']}, "
            f"VIRAL={summary['viral']}, "
            f"Gagal={summary['failed']}"
        )

    except Exception as e:
        logger.error(f"❌ [Analytics IG] Error fatal: {e}")

    return summary


def run_all_trackers():
    """
    Entry point yang dipanggil APScheduler setiap hari jam 23:30 WIB.
    Jalankan kedua tracker secara sekuensial dan log ringkasan akhir.
    """
    logger.info("=" * 60)
    logger.info("🚀 [Analytics] Memulai sesi Auto-Analytics Tracking harian...")
    logger.info("=" * 60)

    yt_summary = update_youtube_stats()
    ig_summary = update_instagram_stats()

    total_low = yt_summary["low_views"] + ig_summary["low_views"]
    total_viral = yt_summary["viral"] + ig_summary["viral"]
    total_updated = yt_summary["updated"] + ig_summary["updated"]

    logger.info(
        f"\n📊 RINGKASAN ANALYTICS HARIAN:\n"
        f"   Total Updated : {total_updated} video\n"
        f"   LOW_VIEWS     : {total_low} video  ← Self-Correction akan aktif besok!\n"
        f"   VIRAL         : {total_viral} video  ← Topik ini mendapat bonus score!\n"
        f"{'=' * 60}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────────────────────────


def _extract_youtube_id(video: PublishedVideo) -> Optional[str]:
    """
    Ekstrak YouTube video ID dari platform_video_id atau URL.
    URL format: https://www.youtube.com/shorts/VIDEO_ID atau https://youtu.be/VIDEO_ID
    """
    if video.platform_video_id:
        return video.platform_video_id

    url = video.video_url or ""
    # Format: https://www.youtube.com/shorts/dQw4w9WgXcQ
    if "/shorts/" in url:
        return url.split("/shorts/")[-1].split("?")[0].strip()
    # Format: https://youtu.be/dQw4w9WgXcQ
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0].strip()
    # Format: https://www.youtube.com/watch?v=dQw4w9WgXcQ
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0].strip()

    return None


def _extract_ig_media_pk(video: PublishedVideo) -> Optional[str]:
    """
    Ekstrak Instagram media PK dari platform_video_id atau URL.
    URL format: https://www.instagram.com/reel/CODE/
    Instagrapi butuh media_pk (integer), yang didapat via media_pk_from_code(code).
    """
    if video.platform_video_id:
        return video.platform_video_id

    url = video.video_url or ""
    if "/reel/" in url:
        code = url.split("/reel/")[-1].strip("/").split("/")[0]
        try:
            from instagrapi import Client

            # Gunakan static method untuk konversi (tidak perlu login)
            cl = Client()
            pk = cl.media_pk_from_code(code)
            return str(pk)
        except Exception:
            return None

    return None


def _boost_viral_topic(topic_name: str):
    """
    Berikan bonus score ke topik yang viral di Redis agar RL agent
    memilihnya lebih sering (eksploitasi momen viral).
    """
    try:
        from data.redis_client import redis_client

        current_data = redis_client.get_topic_score(topic_name)
        old_score = current_data.get("score", 0.0)
        times_chosen = current_data.get("times_chosen", 0)

        # Boost agresif: naikkan score sebesar 20 poin untuk memaksa eksploitasi
        new_score = old_score + 20.0
        redis_client.set_topic_score(topic_name, new_score, times_chosen)

        logger.info(
            f"🚀 [Analytics] Topik VIRAL '{topic_name}' mendapat bonus score! "
            f"{old_score:.1f} → {new_score:.1f}"
        )
    except Exception as e:
        logger.error(f"❌ [Analytics] Gagal boost topik viral '{topic_name}': {e}")


# Singleton (dapat diimpor langsung)
analytics_tracker = type(
    "AnalyticsTracker",
    (),
    {
        "update_youtube": staticmethod(update_youtube_stats),
        "update_instagram": staticmethod(update_instagram_stats),
        "run_all": staticmethod(run_all_trackers),
    },
)()
