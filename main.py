from dotenv import load_dotenv
import os
from pydantic import BaseModel
from tasks import run_rl_pipeline

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from data.redis_client import redis_client
from data.mongodb_client import db
from logger import logger
from contextlib import asynccontextmanager

# FFmpeg Global Injection (Crucial for Windows + Whisper)
try:
    import imageio_ffmpeg

    _ff_exe = imageio_ffmpeg.get_ffmpeg_exe()
    _ff_dir = os.path.dirname(_ff_exe)
    if _ff_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _ff_dir + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("==============================================")
    logger.info("   🤖 AI-CLIP-HUB (GOD-TIER UGC EDITION) 🤖   ")
    logger.info("==============================================")
    logger.info("Arsitektur Sistem: Manual Upload via GDrive + Celery")
    yield
    # Shutdown actions
    logger.info("🛑 Mematikan sistem God-Tier...")
    logger.info("✅ Sistem AI-Clip-Hub mati dengan aman.")


app = FastAPI(
    title="AI-Clip-Hub Dashboard (God-Tier Edition)", version="3.0.0", lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000", 
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/stats")
async def websocket_stats(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket /ws/stats terhubung.")
    try:
        while True:
            topics = redis_client.get_all_topics()
            await websocket.send_text(json.dumps(topics))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass


@app.websocket("/ws/published")
async def websocket_published(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket /ws/published terhubung.")
    try:
        while True:
            try:
                videos = list(
                    db.published_videos.find().sort("published_at", -1).limit(8)
                )
                result = [
                    {
                        "platform": v.get("platform"),
                        "topic_name": v.get("topic_name"),
                        "video_url": v.get("video_url"),
                        "published_at": (
                            v.get("published_at").isoformat()
                            if hasattr(v.get("published_at"), "isoformat")
                            else str(v.get("published_at"))
                        ),
                    }
                    for v in videos
                ]
                await websocket.send_text(json.dumps(result))
            except Exception as e:
                logger.error(f"❌ Error websocket published: {e}")
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket /ws/logs terhubung.")
    log_file_path = "logs/app.log"

    if not os.path.exists(log_file_path):
        os.makedirs("logs", exist_ok=True)
        open(log_file_path, "a", encoding="utf-8").close()

    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.5)
                    continue
                await websocket.send_text(line.strip())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass


class VideoUploadRequest(BaseModel):
    video_path: str
    meta_text_path: str
    title: str
    comment: str
    tags: str
    platform: str


@app.post("/api/actions/trigger-rl")
async def trigger_rl_pipeline():
    """Manual trigger to run the RL Autonomous Engine off-schedule."""
    task = run_rl_pipeline.delay()
    return {
        "message": "RL pipeline manually triggered in background.",
        "task_id": task.id,
    }


@app.post("/api/upload/manual")
async def manual_upload_distribute(req: VideoUploadRequest):
    """API to manually distribute an existing video using the GDrive & Telegram infrastructure."""
    if not os.path.exists(req.video_path):
        return {"error": "Video file not found at local path."}

    from tasks import distribute_and_notify
    task = distribute_and_notify.delay(
        video_path=req.video_path,
        meta_text_path=req.meta_text_path,
        title=req.title,
        comment=req.comment,
        tags=req.tags,
        platform=req.platform,
    )
    return {
        "message": "Distribution task scheduled.",
        "task_id": task.id,
        "platform": req.platform,
    }


@app.get("/api/system/topics")
async def get_active_topics():
    """Retrieve the topics from the RL system."""
    topics = redis_client.get_all_topics()
    return {"status": "success", "topics": topics}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
