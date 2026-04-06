from celery.schedules import crontab
from celery_worker import celery_app

# Jadwal untuk menjalankan pipeline RL ("Autonomous Content Engine") secara kronologis.
# Hal ini menggantikan fungsi APScheduler yang lama dan terintegrasi di luar core application logic.
celery_app.conf.beat_schedule = {
    'run-rl-episode-morning': {
        'task': 'tasks.run_rl_pipeline',
        'schedule': crontab(hour=8, minute=0),
        'args': ()
    },
    'run-rl-episode-afternoon': {
        'task': 'tasks.run_rl_pipeline',
        'schedule': crontab(hour=14, minute=0),
        'args': ()
    },
    'run-rl-episode-evening': {
        'task': 'tasks.run_rl_pipeline',
        'schedule': crontab(hour=19, minute=0),
        'args': ()
    },
}
