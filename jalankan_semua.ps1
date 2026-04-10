$OutputEncoding = [System.Text.Encoding]::UTF8
[console]::InputEncoding = [System.Text.Encoding]::UTF8
[console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  🚀 AI-CLIP-HUB UNIFIED HYBRID SYSTEM (PowerShell)" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Update PATH
$env:PATH = "$PWD\venv\Scripts;$env:PATH"

# 2. Jalankan Celery Worker di Window Baru (Powershell)
Write-Host "[INFO] Menjalankan Celery Worker..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { .\venv\Scripts\Activate.ps1; celery -A celery_worker worker --loglevel=info --pool=solo }"

# 3. Jalankan Hono (Bun) dengan Nodemon
Write-Host "[INFO] Menjalankan Hono API Gateway and Orchestrator di current window..." -ForegroundColor Yellow
Set-Location -Path "ts_engine"
bun install
bun run dev

Read-Host -Prompt "Tekan Enter untuk keluar"
