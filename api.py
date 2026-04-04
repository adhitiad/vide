from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
from data.redis_client import redis_client
from data.mongodb_client import db
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
    <!-- Google Fonts: Outfit & Inter -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">
    
    <!-- Tailwind CSS v4 CDN -->
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <style type="text/tailwindcss">
        @theme {
            --color-primary: #6366f1;
            --color-secondary: #ec4899;
            --color-accent: #10b981;
            --font-display: 'Outfit', sans-serif;
            --font-sans: 'Inter', sans-serif;
        }
        
        body {
            @apply bg-[#030712] text-slate-100 font-sans h-screen flex flex-col p-4 md:p-8 box-border m-0 overflow-hidden;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(236, 72, 153, 0.1) 0px, transparent 50%);
        }

        .glass-card {
            @apply bg-slate-900/40 backdrop-blur-xl rounded-2xl border border-white/10 p-6 flex flex-col overflow-hidden shadow-[0_8px_32px_0_rgba(0,0,0,0.37)];
        }

        h1, h2 { @apply font-display tracking-tight; }

        .terminal {
            @apply flex-1 bg-black/60 text-indigo-300 font-mono p-5 rounded-xl overflow-y-auto text-xs sm:text-sm leading-relaxed whitespace-pre-wrap border border-indigo-500/20 shadow-inner;
        }

        .log-error { @apply text-red-400 font-medium bg-red-400/5 px-2 py-0.5 rounded; }
        .log-warning { @apply text-amber-300 font-medium bg-amber-400/5 px-2 py-0.5 rounded; }
        .log-info { @apply text-slate-400 opacity-90; }
        .log-success { @apply text-emerald-400 font-bold bg-emerald-400/5 px-2 py-0.5 rounded; }

        /* Custom Scrollbar */
        ::-webkit-scrollbar { @apply w-1.5 h-1.5; }
        ::-webkit-scrollbar-track { @apply bg-transparent; }
        ::-webkit-scrollbar-thumb { @apply bg-white/10 rounded-full hover:bg-white/20 transition-all; }

        /* Badge Platforms */
        .badge {
            @apply px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border;
        }
        .badge-yt { @apply bg-red-500/10 text-red-500 border-red-500/30 shadow-[0_0_12px_rgba(239,68,68,0.3)]; }
        .badge-ig { @apply bg-pink-500/10 text-pink-500 border-pink-500/30 shadow-[0_0_12px_rgba(236,72,153,0.3)]; }
        .badge-fb { @apply bg-blue-500/10 text-blue-500 border-blue-500/30 shadow-[0_0_12px_rgba(59,130,246,0.3)]; }
        .badge-tt { @apply bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.3)]; }

        /* Table Design */
        table { @apply w-full border-separate border-spacing-y-2; }
        th { @apply text-slate-500 text-xs font-bold uppercase tracking-widest px-4 pb-2 text-left; }
        td { @apply bg-white/5 px-4 py-3 first:rounded-l-xl last:rounded-r-xl border-y border-white/5 first:border-l last:border-r; }
        tr { @apply hover:translate-x-1 transition-transform duration-300; }
    </style>
</head>
<body>
    <!-- HEADER -->
    <header class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8 shrink-0">
        <div class="flex items-center gap-4">
            <div class="w-14 h-14 bg-gradient-to-tr from-indigo-600 to-pink-500 rounded-2xl flex items-center justify-center text-3xl shadow-lg rotate-3">
                🔥
            </div>
            <div>
                <h1 class="text-3xl font-black bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                    AI-Clip-Hub
                </h1>
                <p class="text-xs font-bold text-indigo-400 tracking-[0.2em] uppercase opacity-80">Autonomous Growth Engine • God-Tier</p>
            </div>
        </div>

        <div id="conn-status" class="bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 px-5 py-2 rounded-2xl text-sm font-bold flex items-center gap-3 backdrop-blur-lg">
            <span class="relative flex h-3 w-3">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            SYSTEM OPERATIONAL
        </div>
    </header>

    <main class="flex flex-col lg:flex-row flex-1 gap-6 overflow-hidden">
        <!-- LEFT: LEADERBOARD -->
        <div class="glass-card w-full lg:w-[400px] border-indigo-500/10">
            <div class="flex items-center justify-between mb-6 border-b border-white/5 pb-4">
                <h2 class="text-xl flex items-center gap-2">
                    <svg class="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                    Topic Intel
                </h2>
                <span class="text-[10px] bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded font-black tracking-tighter">RL ENVT</span>
            </div>
            
            <div class="overflow-y-auto pr-2 custom-scroll">
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Trend Name</th>
                            <th class="text-right">Weight</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboard-body"></tbody>
                </table>
            </div>
        </div>

        <!-- RIGHT: CONSOLE & FEED -->
        <div class="flex-1 flex flex-col gap-6 overflow-hidden">
            <!-- TERMINAL -->
            <div class="glass-card flex-[1.5] border-white/5 relative">
                <div class="flex items-center justify-between mb-4 border-b border-white/5 pb-4">
                     <h2 class="text-xl flex items-center gap-2 text-indigo-300">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                        Neural Engine Logs
                    </h2>
                    <div class="flex gap-2">
                        <div class="w-3 h-3 rounded-full bg-red-500/50"></div>
                        <div class="w-3 h-3 rounded-full bg-amber-500/50"></div>
                        <div class="w-3 h-3 rounded-full bg-emerald-500/50"></div>
                    </div>
                </div>
                <div class="terminal custom-scroll" id="terminal"></div>
                <!-- Scanning Effect Overly -->
                <div class="absolute bottom-0 left-0 right-0 h-1/3 bg-gradient-to-t from-indigo-500/5 to-transparent pointer-events-none"></div>
            </div>

            <!-- LIVE FEED -->
            <div class="glass-card flex-1 border-white/5 bg-gradient-to-br from-slate-900/40 via-transparent to-pink-500/5">
                <h2 class="text-xl flex items-center gap-2 mb-4 text-pink-400">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                    Live Global Distribution
                </h2>
                <div class="overflow-y-auto pr-2 custom-scroll">
                    <table class="w-full">
                        <tbody id="published-body">
                            <tr><td colspan="3" class="text-center py-12 text-slate-600 italic font-medium">Scanning network for publications...</td></tr>
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
            
            data.forEach((topic, index) => {
                const tr = document.createElement('tr');
                const rankColor = index === 0 ? 'text-yellow-400' : index === 1 ? 'text-slate-300' : index === 2 ? 'text-orange-400' : 'text-slate-500';
                
                tr.innerHTML = `
                    <td class="w-12"><span class="font-display ${rankColor} text-lg">#${index + 1}</span></td>
                    <td class="font-semibold text-slate-200">
                        ${topic.name}
                        <div class="text-[9px] text-slate-500 mt-1 flex items-center gap-2">
                             <span class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-indigo-500"></span> SELECT: ${topic.times_chosen}x</span>
                        </div>
                    </td>
                    <td class="text-right font-mono text-indigo-400 font-bold">${topic.score.toFixed(2)}</td>
                `;
                leaderboardBody.appendChild(tr);
            });
        };

        const wsLogs = new WebSocket(`ws://${window.location.host}/ws/logs`);
        const terminal = document.getElementById('terminal');

        wsLogs.onmessage = function(event) {
            const msg = event.data;
            const div = document.createElement('div');
            div.className = 'mb-1 last:mb-0';
            
            if (msg.includes('ERROR') || msg.includes('❌')) div.innerHTML = `<span class="log-error">${msg}</span>`;
            else if (msg.includes('WARNING') || msg.includes('⚠️')) div.innerHTML = `<span class="log-warning">${msg}</span>`;
            else if (msg.includes('✅') || msg.includes('🎯')) div.innerHTML = `<span class="log-success">${msg}</span>`;
            else div.innerHTML = `<span class="log-info">${msg}</span>`;

            terminal.appendChild(div);
            if (terminal.childNodes.length > 300) terminal.removeChild(terminal.firstChild);
            terminal.scrollTop = terminal.scrollHeight;
        };

        const wsPublished = new WebSocket(`ws://${window.location.host}/ws/published`);
        const publishedBody = document.getElementById('published-body');

        wsPublished.onmessage = function(event) {
            const data = JSON.parse(event.data);
            publishedBody.innerHTML = '';

            data.forEach((vid) => {
                const tr = document.createElement('tr');
                const d = new Date(vid.published_at);
                const time = `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
                
                let badgeClass = 'badge-yt';
                if(vid.platform === 'instagram') badgeClass = 'badge-ig';
                if(vid.platform === 'facebook') badgeClass = 'badge-fb';
                if(vid.platform === 'tiktok') badgeClass = 'badge-tt';

                tr.innerHTML = `
                    <td class="w-16"><span class="text-[10px] font-bold text-slate-500 font-mono">${time}</span></td>
                    <td class="w-28"><span class="badge ${badgeClass}">${vid.platform}</span></td>
                    <td class="font-semibold text-slate-300 truncate max-w-[200px]">${vid.topic_name}</td>
                    <td class="text-right">
                        <a href="${vid.video_url}" target="_blank" class="text-indigo-400 hover:text-indigo-300 transition-colors">
                            <svg class="w-6 h-6 inline-block" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                        </a>
                    </td>
                `;
                publishedBody.appendChild(tr);
            });
        };

        function updateStatus(isOnline) {
             const badge = document.getElementById('conn-status');
             badge.className = isOnline ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 px-5 py-2 rounded-2xl text-sm font-bold flex items-center gap-3' : 'bg-red-500/10 text-red-400 border border-red-500/30 px-5 py-2 rounded-2xl text-sm font-bold flex items-center gap-3';
             badge.innerHTML = isOnline ? `<span class="relative flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span></span> SYSTEM OPERATIONAL` : `<span class="w-3 h-3 rounded-full bg-red-500"></span> CONNECTION LOST`;
        }

        wsStats.onclose = () => updateStatus(false);
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
            try:
                videos = list(db.published_videos.find().sort("published_at", -1).limit(8))
                result = [
                    {
                        "platform": v.get("platform"),
                        "topic_name": v.get("topic_name"),
                        "video_url": v.get("video_url"),
                        "published_at": v.get("published_at").isoformat() if hasattr(v.get("published_at"), "isoformat") else str(v.get("published_at")),
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
