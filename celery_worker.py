import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")
redis_password = os.getenv("REDIS_PASSWORD")

broker_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/0"
result_backend = f"redis://:{redis_password}@{redis_host}:{redis_port}/0"

celery_app = Celery(
    "ai_clip_hub",
    broker=broker_url,
    backend=result_backend,
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=False,
    worker_max_tasks_per_child=5,  # Mencegah memory leak karena integrasi dengan library ML/Video
    task_track_started=True,
    broker_connection_retry_on_startup=True
)
