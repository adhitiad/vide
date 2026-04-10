import asyncio
import os
from logger import logger

async def run_ffmpeg_async(args: list[str]):
    """
    Menjalankan FFmpeg secara asynchronous.
    """
    cmd = ["ffmpeg"] + args
    logger.info(f"⚡ Menjalankan Async FFmpeg: {' '.join(cmd)}")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr.decode().strip()
        logger.error(f"❌ FFmpeg Gagal (Exit {process.returncode}): {error_msg}")
        return False
        
    logger.info("✅ FFmpeg Async Selesai.")
    return True

async def extract_audio_async(video_path: str, audio_output: str):
    """Ekstraksi audio cepat menggunakan async ffmpeg"""
    args = [
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        audio_output
    ]
    return await run_ffmpeg_async(args)
