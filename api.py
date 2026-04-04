from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
from data.redis_client import redis_client
from data.database import SessionLocal
from data.models import PublishedVideo
from logger import logger

from contextlib import asynccontextmanager
import threading
from scheduler_control import start_scheduler
from utils.dataset_prep import dataset_prep
from environment.clipper_env import ContentCreatorEnv
import random
import time


def worker_process():
    """
    Loop Otonom (Server ALPHA).
    Sebagai tambahan dari APScheduler (jadwal), ini bisa berjalan konstan sebagai "Spam Bot".
    Berjalan di background thread.
    """
    logger.info("🚀 Memulai Background Worker Process (Hybrid Mode) di dalam API...")
    env = ContentCreatorEnv()
    epsilon = 0.20
    episode = 1

    logger.info("📦 Memeriksa Dataset Fine-Tuning...")
    dataset_prep.check_and_fallback()

    while True:
        try:
            state, _ = env.reset()
            logger.info("--- 🎮 Memulai Episode Hybrid %d ---", episode)

            done = False
            step = 0

            while not done:
                logger.info(f"🔄 Menjalankan Step {step + 1} dari 10...")
                if random.random() < epsilon:
                    action = env.num_actions - 1
                    logger.info(
                        f"🎲 [EKSPLORASI] Memulai riset tren viral Reddit (Aksi terakhir)..."
                    )
                else:
                    best_action_idx = int(state[:-1].argmax()) if len(state) > 1 else 0
                    action = best_action_idx
                    topic, visual = env._decode_action(action)
                    logger.info(
                        f"🎯 [EKSPLOITASI] Memilih aksi terbaik: {topic} (Visual Profil: {visual})"
                    )

                next_state, reward, done, _, _ = env.step(action)
                state = next_state
                step += 1

                # Target: 12 Video Per Hari (Setiap 2 Jam)
                sleep_time = 3645
                logger.info(
                    "⏳ Siklus selesai. Worker tidur selama %d detik...\n", sleep_time
                )
                time.sleep(sleep_time)

            episode += 1
        except Exception as e:
            logger.error(f"❌ Kesalahan saat menjalankan Worker Process: {e}")
            time.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("==============================================")
    logger.info("   🤖 AI-CLIP-HUB (GOD-TIER UGC EDITION) 🤖   ")
    logger.info("==============================================")

    # 1. Start APScheduler in the background
    scheduler = start_scheduler()

    # 2. Start Infinite Worker Process in an OS Thread to avoid blocking asyncio loop
    worker_thread = threading.Thread(
        target=worker_process, daemon=True, name="WorkerThread"
    )
    worker_thread.start()

    yield

    # Shutdown actions
    logger.info("🛑 Mematikan sistem God-Tier...")
    scheduler.shutdown()
    logger.info("✅ Sistem AI-Clip-Hub mati dengan aman.")


app = FastAPI(
    title="AI-Clip-Hub Dashboard (God-Tier Edition)", version="2.0.0", lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Clip-Hub Dashboard (God-Tier)</title>
    <!-- Tailwind CSS v4 CDN -->
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <style type="text/tailwindcss">
        @theme {
            --color-ig: #E1306C;
            --color-yt: #FF0000;
        }
        body {
            @apply bg-slate-950 text-slate-100 font-sans h-screen flex flex-col p-6 box-border m-0 overflow-hidden;
        }
        .glass-panel {
            @apply bg-slate-900/80 backdrop-blur-md rounded-xl border border-slate-700/60 p-5 flex flex-col overflow-hidden shadow-2xl;
        }
        .table-container {
            @apply flex-1 overflow-y-auto pr-2;
        }
        table {
            @apply w-full text-left border-collapse;
        }
        th, td {
            @apply p-3 border-b border-slate-800 text-sm;
        }
        th {
            @apply text-blue-400 font-semibold sticky top-0 bg-slate-900/95 backdrop-blur z-10;
        }
        tr:nth-child(even) {
            @apply bg-white/5;
        }
        tr:hover {
            @apply bg-white/10 transition-colors duration-200;
        }
        /* Mode Terminal */
        .terminal {
            @apply flex-1 bg-black/80 text-emerald-400 font-mono p-4 rounded-lg overflow-y-auto text-xs sm:text-sm leading-relaxed whitespace-pre-wrap shadow-inner border border-slate-800/80;
        }
        .log-error { @apply text-red-500 font-medium; }
        .log-warning { @apply text-amber-400 font-medium; }
        .log-info { @apply text-cyan-400; }
        .log-success { @apply text-emerald-400 font-bold; }
        
        /* Custom scrollbar for webkit */
        ::-webkit-scrollbar { @apply w-2 h-2; }
        ::-webkit-scrollbar-track { @apply bg-slate-900 rounded-full; }
        ::-webkit-scrollbar-thumb { @apply bg-slate-700 rounded-full hover:bg-slate-500 transition-colors; }
    </style>
</head>
<body>
    <header class="flex justify-between items-center pb-5 border-b border-slate-800 mb-6 shrink-0">
        <h1 class="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400 drop-shadow-md flex items-center gap-3">
            <span class="text-3xl">🤖</span> AI-Clip-Hub 
            <span class="text-sm font-medium text-slate-500 tracking-wider uppercase bg-slate-800 px-3 py-1 rounded-full border border-slate-700">(God-Tier UGC Edition)</span>
        </h1>
        <div id="conn-status" class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 px-4 py-1.5 rounded-lg text-sm font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.2)] transition-all duration-300">
            <span class="relative flex h-3 w-3">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            Live API
        </div>
    </header>

    <main class="flex flex-col md:flex-row flex-1 gap-6 overflow-hidden">
        
        <!-- Left Panel: Leaderboard -->
        <div class="glass-panel w-full md:max-w-md">
            <h2 class="text-lg font-bold border-b border-slate-800 pb-3 mb-4 flex items-center gap-2 text-slate-200">
                <span>🏆</span> Leaderboard Sentimen Topik
            </h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th class="w-16">Rank</th>
                            <th>Topik</th>
                            <th class="w-16 text-right">Skor</th>
                            <th class="w-20 text-center">Dipilih</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboard-body">
                        <tr><td colspan="4" class="text-center py-8 text-slate-500">Memuat data sensor sentimen...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="flex flex-1 flex-col gap-6 overflow-hidden">
            <!-- Terminal Panel -->
            <div class="glass-panel flex-[3]">
                <h2 class="text-lg font-bold border-b border-slate-800 pb-3 mb-4 flex items-center gap-2 text-slate-200">
                    <span>💻</span> Terminal Cluster & Spider Network
                </h2>
                <div class="terminal" id="terminal"></div>
            </div>

            <!-- Published Panel -->
            <div class="glass-panel flex-[2] bg-gradient-to-br from-slate-900 to-emerald-950/20 border-emerald-900/30 relative">
                <div class="absolute inset-0 bg-emerald-500/5 blur-3xl rounded-full pointer-events-none"></div>
                <h2 class="text-lg font-bold border-b border-emerald-900/50 pb-3 mb-4 flex items-center gap-2 text-emerald-400 relative z-10">
                    <span>🌍</span> Live Publikasi (YT Shorts & IG Reels)
                </h2>
                <div class="table-container relative z-10">
                    <table>
                        <thead>
                            <tr>
                                <th>Waktu Publikasi</th>
                                <th>Platform</th>
                                <th>Topik Video (Crystal Ball)</th>
                                <th>Tautan</th>
                            </tr>
                        </thead>
                        <tbody id="published-body">
                            <tr><td colspan="4" class="text-center py-6 text-emerald-500/50">Menunggu publikasi otomatis dari jadwal...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <script>
        const wsStats = new WebSocket(`ws://${window.location.host}/ws/stats`);
        const leaderboardBody = document.getElementById('leaderboard-body');

        wsStats.onmessage = function(event) {
            const data = JSON.parse(event.data);
            leaderboardBody.innerHTML = '';

            if (data.length === 0) {
                leaderboardBody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-slate-500 italic">Tidak ada topik viral yang terdeteksi</td></tr>';
                return;
            }

            data.forEach((topic, index) => {
                const tr = document.createElement('tr');
                let rankContent = `<span class="bg-slate-800 text-slate-400 font-bold px-2 py-1 rounded w-8 inline-block text-center">${index + 1}</span>`;
                
                if (index === 0) rankContent = `<span class="bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 font-bold px-2 py-1 rounded w-8 inline-block text-center shadow-[0_0_10px_rgba(234,179,8,0.2)]">🥇</span>`;
                else if (index === 1) rankContent = `<span class="bg-slate-300/20 text-slate-300 border border-slate-300/30 font-bold px-2 py-1 rounded w-8 inline-block text-center">🥈</span>`;
                else if (index === 2) rankContent = `<span class="bg-orange-500/20 text-orange-400 border border-orange-500/30 font-bold px-2 py-1 rounded w-8 inline-block text-center">🥉</span>`;

                tr.innerHTML = `
                    <td>${rankContent}</td>
                    <td class="font-medium text-slate-200">${topic.name}</td>
                    <td class="text-emerald-400 font-mono text-right whitespace-nowrap">${topic.score.toFixed(2)}</td>
                    <td class="text-center"><span class="bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded text-xs font-bold">${topic.times_chosen}x</span></td>
                `;
                leaderboardBody.appendChild(tr);
            });
        };

        const wsLogs = new WebSocket(`ws://${window.location.host}/ws/logs`);
        const terminal = document.getElementById('terminal');

        wsLogs.onmessage = function(event) {
            const msg = event.data;
            const div = document.createElement('div');
            
            if (msg.includes('ERROR') || msg.includes('❌')) {
                div.className = 'log-error';
            } else if (msg.includes('WARNING') || msg.includes('⚠️')) {
                div.className = 'log-warning';
            } else if (msg.includes('✅') || msg.includes('🏆') || msg.includes('🎉') || msg.includes('✨') || msg.includes('🚀') || msg.includes('🎯')) {
                div.className = 'log-success';
            } else {
                div.className = 'log-info';
            }

            div.textContent = msg;
            terminal.appendChild(div);

            if (terminal.childNodes.length > 500) { terminal.removeChild(terminal.firstChild); }
            terminal.scrollTop = terminal.scrollHeight;
        };

        const wsPublished = new WebSocket(`ws://${window.location.host}/ws/published`);
        const publishedBody = document.getElementById('published-body');

        wsPublished.onmessage = function(event) {
            const data = JSON.parse(event.data);
            publishedBody.innerHTML = '';

            if (data.length === 0) {
                publishedBody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-emerald-500/50 italic">Belum ada publikasi otomatis. Sistem sedang bekerja...</td></tr>';
                return;
            }

            data.forEach((vid) => {
                const tr = document.createElement('tr');
                const d = new Date(vid.published_at);
                const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} <span class="text-slate-500 ml-1">${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}</span>`;

                let platformHTML = vid.platform === 'youtube' 
                    ? `<span class="bg-[#FF0000]/20 text-[#FF0000] border border-[#FF0000]/50 px-2.5 py-0.5 rounded shadow-[0_0_8px_rgba(255,0,0,0.2)] text-xs font-bold uppercase tracking-wider">YouTube</span>`
                    : `<span class="bg-[#E1306C]/20 text-[#E1306C] border border-[#E1306C]/50 px-2.5 py-0.5 rounded shadow-[0_0_10px_rgba(225,48,108,0.2)] text-xs font-bold uppercase tracking-wider">Instagram</span>`;

                tr.innerHTML = `
                    <td class="text-slate-400 font-mono text-xs whitespace-nowrap">${dateStr}</td>
                    <td>${platformHTML}</td>
                    <td class="font-medium text-slate-200">${vid.topic_name}</td>
                    <td class="w-24 text-center">
                        <a href="${vid.video_url}" target="_blank" class="inline-flex items-center gap-1 bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded text-xs font-medium transition-colors shadow-xl shadow-blue-500/20 tracking-wide">
                            <span class="text-[10px]">▶</span> Tonton
                        </a>
                    </td>
                `;
                publishedBody.appendChild(tr);
            });
        };

        function updateStatus(isOnline) {
             const badge = document.getElementById('conn-status');
             if(isOnline) { 
                 badge.innerHTML = `<span class="relative flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span></span> Live API`; 
                 badge.className = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 px-4 py-1.5 rounded-lg text-sm font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.2)] transition-all duration-300';
             } else { 
                 badge.innerHTML = `<span class="relative flex h-3 w-3"><span class="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span></span> Terputus`; 
                 badge.className = 'bg-red-500/20 text-red-500 border border-red-500/50 px-4 py-1.5 rounded-lg text-sm font-bold flex items-center gap-2 shadow-[0_0_15px_rgba(239,68,68,0.2)] transition-all duration-300';
             }
        }

        wsStats.onclose = () => updateStatus(false);
        wsLogs.onclose = () => updateStatus(false);
        wsPublished.onclose = () => updateStatus(false);
        wsStats.onerror = () => updateStatus(false);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return HTMLResponse(content=DASHBOARD_HTML, status_code=200)


from fastapi import WebSocketDisconnect


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
            session = SessionLocal()
            try:
                videos = (
                    session.query(PublishedVideo)
                    .order_by(PublishedVideo.published_at.desc())
                    .limit(8)
                    .all()
                )
                result = [
                    {
                        "platform": v.platform,
                        "topic_name": v.topic_name,
                        "video_url": v.video_url,
                        "published_at": v.published_at.isoformat(),
                    }
                    for v in videos
                ]
                await websocket.send_text(json.dumps(result))
            finally:
                session.close()
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
