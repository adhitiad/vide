from dotenv import load_dotenv
import os

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
import multiprocessing
import time
import uvicorn
import random
from logger import logger
from environment.clipper_env import ContentCreatorEnv
from utils.dataset_prep import dataset_prep
from scheduler_control import start_scheduler


import uvicorn
from logger import logger

if __name__ == "__main__":
    logger.info("Mendelegasikan eksekusi ke api.py (Unified Server Edition)...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
