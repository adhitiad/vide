@echo off
chcp 65001 >nul
echo ==================================================
echo   AI-CLIP-HUB UNIFIED HYBRID SYSTEM
echo ==================================================

:: 1. Update PATH
set PATH=%CD%\venv\Scripts;%PATH%

:: 2. Jalankan Celery Worker di Window Baru
echo [INFO] Menjalankan Celery Worker (PowerShell)...
start "Celery Worker (Otot AI)" powershell -NoExit -Command "& { .\venv\Scripts\Activate.ps1; celery -A celery_worker worker --loglevel=info --pool=solo }"

:: 3. Jalankan Hono (Bun) dengan Nodemon
echo [INFO] Menjalankan Hono API Gateway and Orchestrator di current window...
cd ts_engine
call bun install
bun run dev

pause
