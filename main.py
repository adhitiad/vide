import os
import datetime
import asyncio
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from tasks import run_rl_pipeline

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from bson import ObjectId

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from user_agents import parse
import psutil
from typing import Optional, Dict, Any, List
try:
    import GPUtil
except ImportError:
    GPUtil = None

from data.redis_client import redis_client
from data.mongodb_client import db
from logger import logger
from contextlib import asynccontextmanager
from core.security import (
    create_access_token,
    get_current_user,
    require_owner_role,
    verify_password,
)
from core.gdrive_api import gdrive_api

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
async def lifespan(_app: FastAPI):
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
        "http://127.0.0.1:3000",
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_device_id(request: Request) -> str:
    device_id = request.headers.get("X-Device-ID")
    if device_id:
        return device_id
    return get_remote_address(request) # Fallback ke IP

limiter = Limiter(key_func=get_device_id)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.post("/api/login")
@limiter.limit("5/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.users.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Username atau password salah")
    
    access_token = create_access_token(data={"sub": user["username"]})
    
    # Audit Log
    client_ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "unknown")
    db.login_logs.insert_one({
        "username": user["username"],
        "ip": client_ip,
        "user_agent": request.headers.get("User-Agent"),
        "timestamp": datetime.datetime.utcnow()
    })
    
    return {"access_token": access_token, "token_type": "bearer"}


class TrackingRequest(BaseModel):
    platform: str  # "youtube", "instagram", atau "tiktok"
    topic_name: str
    video_url: str  # Link yang Anda copy dari HP setelah upload


class PublishVideoRequest(BaseModel):
    published_url: str


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


@app.post("/api/actions/trigger-rl", dependencies=[Depends(require_owner_role)])
async def trigger_rl_pipeline(current_user: dict = Depends(get_current_user)):
    """Manual trigger to run the RL Autonomous Engine for specific owner."""
    owner_username = current_user.get("username")
    task = run_rl_pipeline.delay(owner_username=owner_username)
    return {
        "message": "RL pipeline manually triggered in background.",
        "task_id": task.id,
    }


# ==========================================
# 🔐 ENDPOINT LOGIN (PUBLIK + RATE LIMIT)
# ==========================================
@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """Endpoint untuk verifikasi username & password via MongoDB, mengembalikan JWT Token."""
    user = db.users.find_one({"username": form_data.username})
    
    if not user or not verify_password(form_data.password, user.get("password")):
        raise HTTPException(
            status_code=401,
            detail="Username atau Password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expiry = user.get("subscription_expiry")
    if expiry and expiry < datetime.datetime.utcnow():
        raise HTTPException(
            status_code=403,
            detail="Masa berlangganan telah habis. Hubungi Admin."
        )

    client_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For") or (request.client.host if request.client else "unknown")
    ua_string = request.headers.get("user-agent", "")
    user_agent = parse(ua_string)
    
    if user_agent.is_mobile: device_type = "Mobile"
    elif user_agent.is_tablet: device_type = "Tablet"
    else: device_type = "Desktop"
    
    device_name = f"{user_agent.device.family} - {user_agent.browser.family} on {user_agent.os.family}"

    location = "Unknown Location"
    try:
        import requests as reqs
        if client_ip != "127.0.0.1" and not client_ip.startswith("192.168"):
            geo_res = reqs.get(f"http://ip-api.com/json/{client_ip}?fields=country,city", timeout=3)
            if geo_res.status_code == 200:
                geo_data = geo_res.json()
                location = f"{geo_data.get('city', 'Unknown')}, {geo_data.get('country', 'Unknown')}"
    except Exception as e:
        logger.warning(f"Gagal melacak lokasi IP {client_ip}: {e}")

    log_data = {
        "username": user["username"],
        "role": user.get("role", "staff"),
        "ip_address": client_ip,
        "device_type": device_type,
        "device_name": device_name,
        "location": location,
        "login_time": datetime.datetime.utcnow()
    }
    db.login_logs.insert_one(log_data)

    access_token = create_access_token(data={"sub": user["username"], "role": user.get("role")})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_info": {
            "username": user["username"],
            "role": user.get("role"),
            "avatar": user.get("avatar")
        }
    }


@app.post("/api/upload/manual")
async def manual_upload_distribute(req: VideoUploadRequest, current_user: dict = Depends(get_current_user)):
    """API to manually distribute an existing video using the GDrive & Telegram infrastructure."""
    owner_username = current_user.get("username")
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
        owner_username=owner_username,
    )
    return {
        "message": "Distribution task scheduled.",
        "task_id": task.id,
        "platform": req.platform,
    }


@app.get("/api/videos/waiting")
async def get_waiting_videos(current_user: dict = Depends(get_current_user)):
    """Mengambil daftar video milik user yang siap di-download dan menunggu URL."""
    owner_username = current_user.get("username")
    try:
        videos = list(
            db.published_videos.find(
                {
                    "owner_username": owner_username,
                    "performance_status": {
                        "$in": ["WAITING_UPLOAD", "ACTION_REQUIRED_RED"]
                    }
                }
            ).sort("created_at", -1)
        )
        # Konversi ObjectId ke string agar bisa dibaca JSON frontend
        for v in videos:
            v["_id"] = str(v["_id"])
        return {"status": "success", "data": videos}
    except Exception as e:
        logger.error(f"Error fetching waiting videos: {e}")
        return {"status": "error", "message": str(e)}


@app.put("/api/videos/{video_id}/publish")
async def update_published_url(video_id: str, req: PublishVideoRequest, current_user: dict = Depends(get_current_user)):
    """
    Endpoint yang dipanggil saat User menekan tombol 'Submit URL' di Dashboard.
    """
    owner_username = current_user.get("username")
    try:
        # 1. Cari data video milik owner tersebut
        video = db.published_videos.find_one({"_id": ObjectId(video_id), "owner_username": owner_username})
        if not video:
            raise HTTPException(status_code=404, detail="Video tidak ditemukan.")

        # 2. Update MongoDB
        db.published_videos.update_one(
            {"_id": ObjectId(video_id)},
            {
                "$set": {
                    "video_url": req.published_url,
                    "performance_status": "PENDING",  # Status ini yang dicari oleh analytics_tracker
                    "published_at": datetime.datetime.utcnow(),
                    "last_checked": datetime.datetime.utcnow(),
                }
            },
        )

        # 3. AUTO-CLEANUP GDrive (Hemat Kuota)
        gdrive_link = video.get("gdrive_link", "")
        if gdrive_link:
            try:
                # Ekstrak ID dari URL
                # Contoh: https://drive.google.com/open?id=... atau https://drive.google.com/file/d/.../view
                file_id = None
                if "/d/" in gdrive_link:
                    file_id = gdrive_link.split("/d/")[1].split("/")[0]
                elif "id=" in gdrive_link:
                    file_id = gdrive_link.split("id=")[1].split("&")[0]

                if file_id:
                    # Panggil service GDrive untuk menghapus file
                    # Catatan: Ini mengasumsikan gdrive_api memiliki attribute 'service' yang bisa diakses
                    # Jika gdrive_api.service tidak publik, kita mungkin perlu metode di gdrive_api
                    # Namun mengikuti saran Gemini yang menggunakan gdrive_api.service.files().delete()
                    if hasattr(gdrive_api, "service"):
                        gdrive_api.service.files().delete(fileId=file_id).execute()
                        logger.info(
                            f"🗑️ File Master Video dihapus dari GDrive untuk menghemat kuota."
                        )
                    else:
                        # Fallback jika kita perlu menggunakan metode async yang ada
                        logger.warning(
                            "⚠️ gdrive_api.service tidak ditemukan, cleanup dilompati."
                        )
            except Exception as e:
                logger.warning(f"⚠️ Gagal menghapus dari GDrive otomatis: {e}")

        logger.info(
            f"✅ Video {video_id} berhasil didaftarkan dengan URL: {req.published_url}"
        )
        return {
            "status": "success",
            "message": "URL berhasil disimpan! GDrive dibersihkan & Analytics akan melacak video ini.",
        }

    except Exception as e:
        logger.error(f"Gagal update URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/videos/{video_id}/red-list-action")
async def red_list_action(video_id: str, action: str, current_user: dict = Depends(get_current_user)):
    """
    Menangani keputusan User untuk video Daftar Merah.
    """
    owner_username = current_user.get("username")
    try:
        if action == "hapus":
            db.published_videos.delete_one({"_id": ObjectId(video_id), "owner_username": owner_username})
            return {
                "status": "success",
                "message": "Video Daftar Merah dihapus dari database.",
            }

        elif action == "simpan":
            db.published_videos.update_one(
                {"_id": ObjectId(video_id), "owner_username": owner_username},
                {"$set": {"performance_status": "ARCHIVED_RED_LIST"}},
            )
            return {"status": "success", "message": "Video disimpan ke arsip."}

        elif action == "upload":
            db.published_videos.update_one(
                {"_id": ObjectId(video_id), "owner_username": owner_username},
                {"$set": {"performance_status": "WAITING_UPLOAD"}},
            )
            return {
                "status": "success",
                "message": "Video dipindahkan ke antrean Upload.",
            }

        else:
            raise HTTPException(status_code=400, detail="Aksi tidak valid.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/topics")
async def get_active_topics():
    """Retrieve the topics from the RL system."""
    topics = redis_client.get_all_topics()
    return {"status": "success", "topics": topics}


@app.post("/api/system/register-tracking")
async def register_video_for_tracking(req: TrackingRequest, current_user: dict = Depends(get_current_user)):
    """
    Endpoint agar Anda bisa mendaftarkan link video yang baru saja
    Anda upload manual agar bisa dilacak oleh analytics_tracker.py
    """
    owner_username = current_user.get("username")
    try:
        new_video = {
            "owner_username": owner_username,
            "platform": req.platform,
            "topic_name": req.topic_name,
            "video_url": req.video_url,
            "published_at": datetime.datetime.utcnow(),
            "views": 0,
            "likes": 0,
            "comments": 0,
            "performance_status": "PENDING",
            "last_checked": datetime.datetime.utcnow(),
        }

        # Simpan ke MongoDB agar nanti malam dibaca oleh analytics_tracker.py
        db.published_videos.insert_one(new_video)

        return {
            "status": "success",
            "message": f"Video {req.platform} terdaftar untuk Analytics!",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


class TrackEventRequest(BaseModel):
    event_name: str
    event_data: Optional[Dict[str, Any]] = {}
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    referrer: Optional[str] = None

class ChatMessageRequest(BaseModel):
    message: str

@app.post("/api/track/event", dependencies=[Depends(get_current_user)])
async def track_user_event(
    req: TrackEventRequest, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    try:
        client_ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "unknown")
        event_doc = {
            "username": current_user["username"],
            "role": current_user.get("role", "staff"),
            "event_name": req.event_name,
            "event_data": req.event_data,
            "marketing_data": {
                "utm_source": req.utm_source,
                "utm_medium": req.utm_medium,
                "utm_campaign": req.utm_campaign,
                "referrer": req.referrer,
            },
            "ip_address": client_ip,
            "timestamp": datetime.datetime.utcnow()
        }
        db.user_events.insert_one(event_doc)
        return {"status": "success", "message": "Event recorded"}
    except Exception as e:
        logger.error(f"Gagal melacak event: {e}")
        return {"status": "error", "message": "Tracking failed silently"}

@app.post("/api/chat", dependencies=[Depends(get_current_user)])
async def chat_with_bot(req: ChatMessageRequest, current_user: dict = Depends(get_current_user)):
    from core.chatbot_agent import get_chatbot_response
    user_msg = req.message
    username = current_user["username"]
    bot_result = get_chatbot_response(user_msg, username)
    
    db.chat_logs.insert_one({
        "username": username,
        "role": current_user.get("role", "staff"),
        "user_input": user_msg,
        "bot_response": bot_result["response"],
        "actions_taken": bot_result["actions_taken"],
        "timestamp": datetime.datetime.utcnow()
    })
    return {
        "status": "success", 
        "reply": bot_result["response"],
        "actions": bot_result["actions_taken"]
    }

@app.get("/api/system/health/ultimate", dependencies=[Depends(require_owner_role)])
async def get_ultimate_system_health():
    health_data = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "status": "HEALTHY",
        "alerts": []
    }
    ram = psutil.virtual_memory()
    hardware = {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_percent": ram.percent,
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "disk_percent": psutil.disk_usage('/').percent,
        "gpu": "Tidak Terdeteksi"
    }
    if ram.percent > 90:
        health_data["status"] = "WARNING"
        health_data["alerts"].append("RAM Server Kritis (>90%)!")
    if GPUtil:
        gpus = GPUtil.getGPUs()
        if gpus:
            hardware["gpu"] = f"{gpus[0].name} (Load: {gpus[0].load*100}%, VRAM: {gpus[0].memoryUtil*100}%)"
    health_data["hardware"] = hardware

    try:
        db.command("ping")
        health_data["mongodb"] = {
            "status": "Connected",
            "total_users": db.users.count_documents({}),
            "total_videos_rendered": db.published_videos.count_documents({}),
            "pending_uploads": db.published_videos.count_documents({"performance_status": "WAITING_UPLOAD"})
        }
    except Exception as e:
        health_data["status"] = "CRITICAL"
        health_data["alerts"].append("MongoDB Terputus!")
        health_data["mongodb"] = {"status": "Disconnected", "error": str(e)}

    try:
        if hasattr(redis_client, "_client") and redis_client._client:
            redis_client._client.ping()
            health_data["redis_celery"] = {
                "status": "Connected",
                "tasks_in_queue": redis_client._client.llen("celery")
            }
        else:
            health_data["redis_celery"] = {
                "status": "Disabled",
                "tasks_in_queue": 0
            }
    except Exception as e:
        health_data["status"] = "CRITICAL"
        health_data["alerts"].append("Redis Broker Terputus! Rendering Macet.")
        health_data["redis_celery"] = {"status": "Disconnected", "error": str(e)}

    recent_errors = list(db.system_logs.find({"level": "ERROR"}).sort("timestamp", -1).limit(5)) if "system_logs" in db.list_collection_names() else []
    health_data["recent_errors"] = [
        {"time": err.get("timestamp", datetime.datetime.utcnow()).strftime("%H:%M:%S"), "message": err.get("message", "Unknown")} 
        for err in recent_errors
    ]
    return health_data

@app.post("/api/system/action", dependencies=[Depends(require_owner_role)])
async def system_action(req: dict, current_user: dict = Depends(get_current_user)):
    """Handle critical system actions from the GodModePanel."""
    action = req.get("action")
    owner_username = current_user.get("username")
    
    logger.warning(f"⚠️ [SYSTEM] Admin {owner_username} memicu aksi: {action}")
    
    if action == "FLUSH_REDIS":
        try:
            if hasattr(redis_client, "_client") and redis_client._client:
                redis_client._client.flushall()
                logger.info("🧹 Redis Cache dibersihkan sepenuhnya.")
                return {"status": "success", "message": "Redis flushed successfully."}
            return {"status": "error", "message": "Redis client not connected."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    elif action == "RESTART_WORKER":
        try:
            if hasattr(redis_client, "_client") and redis_client._client:
                # Mengirim sinyal via Redis untuk diproses oleh worker
                redis_client._client.set("SYSTEM_SIGNAL_RESTART", "1", ex=60)
                logger.info("🔄 Sinyal restart dikirim via Redis.")
                return {"status": "success", "message": "Restart signal broadcasting..."}
            return {"status": "error", "message": "Redis not found."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "Aksi tidak dikenal."}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
