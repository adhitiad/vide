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

app = FastAPI(title="AI-Clip-Hub Dashboard (God-Tier Edition)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    <style>
        :root {
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --text-color: #f8fafc;
            --primary-color: #3b82f6;
            --accent-color: #10b981;
            --ig-color: #E1306C;
            --yt-color: #FF0000;
            --border-color: #334155;
            --font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: var(--font-family);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            height: 100vh;
            box-sizing: border-box;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 20px;
        }

        h1 { margin: 0; font-size: 24px; color: var(--primary-color); }

        .status-badge {
            background-color: var(--accent-color);
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 14px;
            font-weight: bold;
        }

        main { display: flex; flex: 1; gap: 20px; overflow: hidden; }

        .panel {
            background-color: var(--panel-bg);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            padding: 20px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .left-panel { flex: 1; max-width: 400px; }
        .right-panel { flex: 2; display: flex; flex-direction: column; gap: 20px; }

        h2 { margin-top: 0; font-size: 18px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 15px; }

        .table-container { flex: 1; overflow-y: auto; }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th, td { padding: 10px; border-bottom: 1px solid var(--border-color); }
        th { color: var(--primary-color); font-weight: 600; }
        tr:nth-child(even) { background-color: rgba(255, 255, 255, 0.05); }

        a { color: var(--accent-color); text-decoration: none; }
        a:hover { text-decoration: underline; }

        .platform-badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            color: white;
            text-transform: uppercase;
        }

        .terminal {
            flex: 2;
            background-color: #000;
            color: #0f0;
            font-family: 'Courier New', Courier, monospace;
            padding: 15px;
            border-radius: 5px;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
            min-height: 300px;
        }

        .log-line { margin: 0; }
        .log-error { color: #ff4444; }
        .log-warning { color: #ffbb33; }
        .log-info { color: #33b5e5; }
        .log-success { color: #00C851; }
        .published-panel { flex: 1; background-color: rgba(16, 185, 129, 0.05); border: 1px solid var(--accent-color); min-height: 200px; }
    </style>
</head>
<body>
    <header>
        <h1>🤖 AI-Clip-Hub <span style="font-size:14px; color:#94a3b8;">(God-Tier UGC Edition)</span></h1>
        <div class="status-badge" id="conn-status">🟢 Live API</div>
    </header>

    <main>
        <div class="panel left-panel">
            <h2>🏆 Leaderboard Sentimen Topik</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Topik</th>
                            <th>Skor</th>
                            <th>Dipilih</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboard-body">
                        <tr><td colspan="4" style="text-align:center;">Memuat data...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="right-panel">
            <div class="panel" style="flex: 2;">
                <h2>💻 Terminal Cluster & Spider Network</h2>
                <div class="terminal" id="terminal"></div>
            </div>

            <div class="panel published-panel" style="flex: 1;">
                <h2 style="color: var(--accent-color);">🌍 Live Publikasi (YT Shorts & IG Reels)</h2>
                <div class="table-container">
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
                            <tr><td colspan="4" style="text-align:center;">Menunggu publikasi otomatis dari jadwal...</td></tr>
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
                leaderboardBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Tidak ada topik</td></tr>';
                return;
            }

            data.forEach((topic, index) => {
                const tr = document.createElement('tr');
                let rankText = index + 1;
                if(index === 0) rankText = '🥇 ' + rankText;
                else if(index === 1) rankText = '🥈 ' + rankText;
                else if(index === 2) rankText = '🥉 ' + rankText;

                tr.innerHTML = `
                    <td>${rankText}</td>
                    <td><strong>${topic.name}</strong></td>
                    <td style="color:var(--accent-color)">${topic.score.toFixed(2)}</td>
                    <td>${topic.times_chosen}x</td>
                `;
                leaderboardBody.appendChild(tr);
            });
        };

        const wsLogs = new WebSocket(`ws://${window.location.host}/ws/logs`);
        const terminal = document.getElementById('terminal');

        wsLogs.onmessage = function(event) {
            const msg = event.data;
            const div = document.createElement('div');
            div.className = 'log-line';

            if (msg.includes('ERROR') || msg.includes('❌')) {
                div.classList.add('log-error');
            } else if (msg.includes('WARNING') || msg.includes('⚠️')) {
                div.classList.add('log-warning');
            } else if (msg.includes('✅') || msg.includes('🏆') || msg.includes('🎉') || msg.includes('✨')) {
                div.classList.add('log-success');
            } else {
                div.classList.add('log-info');
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
                publishedBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Belum ada publikasi otomatis.</td></tr>';
                return;
            }

            data.forEach((vid) => {
                const tr = document.createElement('tr');
                const d = new Date(vid.published_at);
                const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;

                let platformColor = vid.platform === 'youtube' ? 'var(--yt-color)' : 'var(--ig-color)';

                tr.innerHTML = `
                    <td style="font-size: 13px; color: #94a3b8;">${dateStr}</td>
                    <td><span class="platform-badge" style="background-color: ${platformColor}">${vid.platform}</span></td>
                    <td><strong>${vid.topic_name}</strong></td>
                    <td><a href="${vid.video_url}" target="_blank">🔗 Tonton</a></td>
                `;
                publishedBody.appendChild(tr);
            });
        };

        function updateStatus(isOnline) {
             const badge = document.getElementById('conn-status');
             if(isOnline) { badge.textContent = '🟢 Live API'; badge.style.backgroundColor = 'var(--accent-color)'; }
             else { badge.textContent = '🔴 Terputus'; badge.style.backgroundColor = '#ef4444'; }
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

@app.websocket("/ws/stats")
async def websocket_stats(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket /ws/stats terhubung.")
    try:
        while True:
            topics = redis_client.get_all_topics()
            await websocket.send_text(json.dumps(topics))
            await asyncio.sleep(2)
    except Exception as e:
         pass
    finally:
         await websocket.close()

@app.websocket("/ws/published")
async def websocket_published(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket /ws/published terhubung.")
    try:
        while True:
            session = SessionLocal()
            try:
                videos = session.query(PublishedVideo).order_by(PublishedVideo.published_at.desc()).limit(8).all()
                result = [
                    {
                        "platform": v.platform,
                        "topic_name": v.topic_name,
                        "video_url": v.video_url,
                        "published_at": v.published_at.isoformat()
                    } for v in videos
                ]
                await websocket.send_text(json.dumps(result))
            finally:
                session.close()
            await asyncio.sleep(5)
    except Exception as e:
         pass
    finally:
         await websocket.close()

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket /ws/logs terhubung.")
    log_file_path = "logs/app.log"

    if not os.path.exists(log_file_path):
        open(log_file_path, 'a').close()

    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.5)
                    continue
                await websocket.send_text(line.strip())
    except Exception as e:
        pass
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
