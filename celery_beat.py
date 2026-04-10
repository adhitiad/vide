from celery.schedules import crontab
from celery_worker import celery_app

# ========================================================================
# AI-CLIP-HUB : JADWAL OTOMATIS (GOD-TIER SaaS EDITION)
# ========================================================================
# Celery Beat akan menjalankan semua tugas ini secara otomatis.
# Semua jadwal menggunakan timezone Asia/Jakarta (sudah diset di celery_worker.py).
#
# PENTING: Semua pipeline RL kini menggunakan "run_all_active_pipelines"
# yang secara otomatis meloop semua user aktif dari database.
# Tidak perlu lagi hardcode username di sini.
# ========================================================================

celery_app.conf.beat_schedule = {

    # ==========================================
    # 🎬 PRODUKSI KONTEN HARIAN (3x Sehari)
    # ==========================================
    # Menjalankan pipeline RL untuk SEMUA user aktif di database.
    'multi-tenant-pipeline-morning': {
        'task': 'tasks.run_all_active_pipelines',
        'schedule': crontab(hour=8, minute=0),
    },
    'multi-tenant-pipeline-afternoon': {
        'task': 'tasks.run_all_active_pipelines',
        'schedule': crontab(hour=14, minute=0),
    },
    'multi-tenant-pipeline-evening': {
        'task': 'tasks.run_all_active_pipelines',
        'schedule': crontab(hour=19, minute=0),
    },

    # ==========================================
    # 📡 TREND-JACKING RADAR (Setiap 6 Jam)
    # ==========================================
    # Memantau berita viral dan mencocokkan dengan niche user.
    # Jika cocok, langsung trigger produksi video instan.
    'trend-jacking-radar': {
        'task': 'tasks.run_trend_jacking_radar',
        'schedule': crontab(hour='*/6', minute=15),
    },

    # ==========================================
    # 📊 WEEKLY ROI REPORT (Minggu, 09:00 WIB)
    # ==========================================
    # Mengirim laporan performa mingguan ke Owner via WhatsApp.
    'weekly-roi-report': {
        'task': 'tasks.generate_weekly_roi_report',
        'schedule': crontab(hour=9, minute=0, day_of_week='sunday'),
    },

    # ==========================================
    # 🧹 AUTO-EXPIRE LANGGANAN (Setiap Hari, 00:01 WIB)
    # ==========================================
    # Menonaktifkan akun yang langganannya sudah melewati batas waktu.
    'auto-expire-subscriptions': {
        'task': 'tasks.auto_expire_subscriptions',
        'schedule': crontab(hour=0, minute=1),
    },

}
