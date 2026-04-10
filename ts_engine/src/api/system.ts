import { Hono } from 'hono';
import { getDb } from '../db/mongo';
import { requireAuth, requireOwnerRole } from './middleware';
import si from 'systeminformation';
import { redisClient } from '../queue/celery';

export const systemApp = new Hono();

// Tracking
systemApp.post('/register-tracking', requireAuth, async (c) => {
  const user = c.get('user' as never) as any;
  const db = getDb();
  
  try {
    const req = await c.req.json();
    
    const newVideo = {
      owner_username: user.username,
      platform: req.platform,
      topic_name: req.topic_name,
      video_url: req.video_url,
      published_at: new Date(),
      views: 0,
      likes: 0,
      comments: 0,
      performance_status: "PENDING",
      last_checked: new Date()
    };
    
    await db.collection('published_videos').insertOne(newVideo);
    
    return c.json({
      status: "success",
      message: `Video ${req.platform} terdaftar untuk Analytics!`
    });
  } catch (error: any) {
    return c.json({ status: "error", message: error.message }, 500);
  }
});

systemApp.post('/track/event', requireAuth, async (c) => {
  const user = c.get('user' as never) as any;
  const db = getDb();

  try {
    const req = await c.req.json();
    const clientIp = c.req.header('CF-Connecting-IP') || 'unknown';

    const eventDoc = {
      username: user.username,
      role: user.role || 'staff',
      event_name: req.event_name,
      event_data: req.event_data || {},
      marketing_data: {
        utm_source: req.utm_source,
        utm_medium: req.utm_medium,
        utm_campaign: req.utm_campaign,
        referrer: req.referrer
      },
      ip_address: clientIp,
      timestamp: new Date()
    };
    
    await db.collection('user_events').insertOne(eventDoc);
    return c.json({ status: "success", message: "Event recorded" });
  } catch (error: any) {
    console.error("Gagal melacak event:", error);
    return c.json({ status: "error", message: "Tracking failed silently" }, 500);
  }
});

// System Status
systemApp.get('/health/ultimate', requireOwnerRole, async (c) => {
  const db = getDb();
  
  const healthData: any = {
    timestamp: new Date().toISOString(),
    status: "HEALTHY",
    alerts: []
  };

  try {
    const mem = await si.mem();
    const cpu = await si.currentLoad();
    const disk = await si.fsSize();
    const diskPercent = disk.length > 0 ? disk[0].use : 0;
    
    const ramPercent = (mem.used / mem.total) * 100;

    healthData.hardware = {
      cpu_percent: cpu.currentLoad,
      ram_percent: ramPercent,
      ram_used_gb: Math.round(mem.used / (1024 ** 3) * 100) / 100,
      disk_percent: diskPercent,
      gpu: "Tidak Terdeteksi" 
    };

    if (ramPercent > 90) {
      healthData.status = "WARNING";
      healthData.alerts.push("RAM Server Kritis (>90%)!");
    }

    // Ping mongo
    await db.command({ ping: 1 });
    healthData.mongodb = {
      status: "Connected",
      total_users: await db.collection('users').countDocuments(),
      total_videos_rendered: await db.collection('published_videos').countDocuments(),
      pending_uploads: await db.collection('published_videos').countDocuments({ performance_status: "WAITING_UPLOAD" })
    };
  } catch (error: any) {
    healthData.status = "CRITICAL";
    healthData.alerts.push("MongoDB Terputus!");
    healthData.mongodb = { status: "Disconnected", error: error.message };
  }

  try {
    await redisClient.ping();
    const queueLen = await redisClient.llen('celery');
    healthData.redis_celery = {
      status: "Connected",
      tasks_in_queue: queueLen
    };
  } catch (error: any) {
    healthData.status = "CRITICAL";
    healthData.alerts.push("Redis Broker Terputus! Rendering Macet.");
    healthData.redis_celery = { status: "Disconnected", error: error.message };
  }

  try {
    const recentErrors = await db.collection('system_logs')
      .find({ level: "ERROR" })
      .sort({ timestamp: -1 })
      .limit(5)
      .toArray();

    healthData.recent_errors = recentErrors.map(err => ({
      time: err.timestamp ? err.timestamp.toISOString() : "Unknown",
      message: err.message || "Unknown"
    }));
  } catch (error) {
    healthData.recent_errors = [];
  }

  return c.json(healthData);
});

// System Actions
systemApp.post('/action', requireOwnerRole, async (c) => {
  const user = c.get('user' as never) as any;
  
  try {
    const req = await c.req.json();
    const action = req.action;

    console.warn(`⚠️ [SYSTEM] Admin ${user.username} memicu aksi: ${action}`);

    if (action === "FLUSH_REDIS") {
      await redisClient.flushall();
      console.log("🧹 Redis Cache dibersihkan sepenuhnya.");
      return c.json({ status: "success", message: "Redis flushed successfully." });
    } else if (action === "RESTART_WORKER") {
      await redisClient.setex("SYSTEM_SIGNAL_RESTART", 60, "1");
      console.log("🔄 Sinyal restart dikirim via Redis.");
      return c.json({ status: "success", message: "Restart signal broadcasting..." });
    }

    return c.json({ status: "error", message: "Aksi tidak dikenal." }, 400);
  } catch (error: any) {
    return c.json({ status: "error", message: error.message }, 500);
  }
});
