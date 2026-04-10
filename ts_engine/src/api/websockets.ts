import { Hono } from 'hono';
import { createBunWebSocket } from 'hono/bun';
import { redisClient } from '../queue/celery';
import { getDb } from '../db/mongo';
import fs from 'fs';
import path from 'path';

export const wsApp = new Hono();
const { upgradeWebSocket, websocket } = createBunWebSocket();

export const bunWebsocket = websocket;

wsApp.get(
  '/stats',
  upgradeWebSocket((c) => {
    let interval: Timer;
    return {
      onOpen(_event, ws) {
        console.log('🔌 WebSocket /ws/stats terhubung.');
        interval = setInterval(async () => {
          try {
            // Using a simple KEYS * for legacy topic structure or a SET in python
            const keys = await redisClient.keys('topic:*');
            const topics = [];
            for (const key of keys) {
              topics.push(await redisClient.hgetall(key));
            }
            ws.send(JSON.stringify(topics));
          } catch (e) {
            // ignore
          }
        }, 2000);
      },
      onClose() {
        clearInterval(interval);
      },
      onError(err) {
        console.error("WS error:", err);
      }
    };
  })
);

wsApp.get(
  '/published',
  upgradeWebSocket((c) => {
    let interval: Timer;
    return {
      onOpen(_event, ws) {
        console.log('🔌 WebSocket /ws/published terhubung.');
        interval = setInterval(async () => {
          try {
            const db = getDb();
            const videos = await db.collection('published_videos')
              .find()
              .sort({ published_at: -1 })
              .limit(8)
              .toArray();
            
            const result = videos.map(v => ({
              platform: v.platform,
              topic_name: v.topic_name,
              video_url: v.video_url,
              published_at: v.published_at ? new Date(v.published_at).toISOString() : null
            }));
            
            ws.send(JSON.stringify(result));
          } catch (e) {
            console.error('❌ Error websocket published:', e);
          }
        }, 5000);
      },
      onClose() {
        clearInterval(interval);
      }
    };
  })
);

wsApp.get(
  '/logs',
  upgradeWebSocket((c) => {
    let interval: Timer;
    let bytesRead = 0;
    return {
      onOpen(_event, ws) {
        console.log('🔌 WebSocket /ws/logs terhubung.');
        const logFilePath = path.resolve(__dirname, '../../../../logs/app.log');
        
        // Ensure folder and file exist
        if (!fs.existsSync(logFilePath)) {
          const dir = path.dirname(logFilePath);
          if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
          fs.writeFileSync(logFilePath, '');
        }

        try {
          // Send only new lines dynamically matching a simple `tail -f`
          const stats = fs.statSync(logFilePath);
          bytesRead = stats.size; // start at EOF
          
          interval = setInterval(() => {
            const currentStats = fs.statSync(logFilePath);
            if (currentStats.size > bytesRead) {
              const buffer = Buffer.alloc(currentStats.size - bytesRead);
              const fd = fs.openSync(logFilePath, 'r');
              fs.readSync(fd, buffer, 0, buffer.length, bytesRead);
              fs.closeSync(fd);
              
              const newContent = buffer.toString('utf-8');
              const lines = newContent.split('\n');
              for (const line of lines) {
                if (line.trim()) {
                  ws.send(line.trim());
                }
              }
              bytesRead = currentStats.size;
            }
          }, 500);

        } catch (e) {
          console.error("Failed to tail logs:", e);
        }
      },
      onClose() {
        clearInterval(interval);
      }
    };
  })
);
