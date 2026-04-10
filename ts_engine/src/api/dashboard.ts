import { Hono } from 'hono';
import { getDb } from '../db/mongo';
import { requireAuth, requireOwnerRole } from './middleware';
import { ObjectId } from 'mongodb';
import { triggerCeleryTask } from '../queue/celery';

export const dashboardApp = new Hono();

// Middlewares
dashboardApp.use('/*', requireAuth);

dashboardApp.get('/videos/waiting', async (c) => {
  const user = c.get('user' as never) as any;
  const db = getDb();
  
  try {
    const videos = await db.collection('published_videos').find({
      owner_username: user.username,
      performance_status: { $in: ["WAITING_UPLOAD", "ACTION_REQUIRED_RED"] }
    }).sort({ created_at: -1 }).toArray();

    // Mapping ObjectId to string
    const formattedVideos = videos.map(v => ({
      ...v,
      _id: v._id.toString()
    }));

    return c.json({ status: "success", data: formattedVideos });
  } catch (error: any) {
    console.error("Error fetching waiting videos:", error);
    return c.json({ status: "error", message: error.message }, 500);
  }
});

dashboardApp.put('/videos/:video_id/publish', async (c) => {
  const user = c.get('user' as never) as any;
  const video_id = c.req.param('video_id');
  const db = getDb();
  
  try {
    const body = await c.req.json();
    const published_url = body.published_url;

    if (!ObjectId.isValid(video_id)) {
      return c.json({ detail: "Video ID tidak valid." }, 400);
    }

    const video = await db.collection('published_videos').findOne({
      _id: new ObjectId(video_id),
      owner_username: user.username
    });

    if (!video) {
      return c.json({ detail: "Video tidak ditemukan." }, 404);
    }

    await db.collection('published_videos').updateOne(
      { _id: new ObjectId(video_id) },
      {
        $set: {
          video_url: published_url,
          performance_status: "PENDING",
          published_at: new Date(),
          last_checked: new Date()
        }
      }
    );

    // Skip GDrive auto cleanup for now, as GDrive API is tied down to python packages right now.
    // In actual production, you can port GDrive API to node.js or trigger celery cleanup task.
    console.log(`✅ Video ${video_id} berhasil didaftarkan dengan URL: ${published_url}`);

    return c.json({
      status: "success",
      message: "URL berhasil disimpan! Analytics akan melacak video ini."
    });
  } catch (error: any) {
    console.error("Gagal update URL:", error);
    return c.json({ detail: error.message }, 500);
  }
});

dashboardApp.put('/videos/:video_id/red-list-action', async (c) => {
  const user = c.get('user' as never) as any;
  const video_id = c.req.param('video_id');
  const db = getDb();

  try {
    const action = c.req.query('action');
    if (!ObjectId.isValid(video_id)) {
      return c.json({ detail: "Video ID tidak valid." }, 400);
    }

    const filter = { _id: new ObjectId(video_id), owner_username: user.username };

    if (action === "hapus") {
      await db.collection('published_videos').deleteOne(filter);
      return c.json({ status: "success", message: "Video Daftar Merah dihapus dari database." });
    } else if (action === "simpan") {
      await db.collection('published_videos').updateOne(filter, { $set: { performance_status: "ARCHIVED_RED_LIST" } });
      return c.json({ status: "success", message: "Video disimpan ke arsip." });
    } else if (action === "upload") {
      await db.collection('published_videos').updateOne(filter, { $set: { performance_status: "WAITING_UPLOAD" } });
      return c.json({ status: "success", message: "Video dipindahkan ke antrean Upload." });
    } else {
      return c.json({ detail: "Aksi tidak valid." }, 400);
    }
  } catch (error: any) {
    return c.json({ detail: error.message }, 500);
  }
});

dashboardApp.post('/upload/manual', async (c) => {
  const user = c.get('user' as never) as any;
  try {
    const req = await c.req.json();
    
    // trigger python celery task
    const task_id = await triggerCeleryTask('tasks.distribute_and_notify', {
      video_path: req.video_path,
      meta_text_path: req.meta_text_path,
      title: req.title,
      comment: req.comment,
      tags: req.tags,
      platform: req.platform,
      owner_username: user.username,
    });

    return c.json({
      message: "Distribution task scheduled.",
      task_id: task_id,
      platform: req.platform
    });
  } catch (error: any) {
    return c.json({ error: error.message }, 500);
  }
});

dashboardApp.post('/actions/trigger-rl', requireOwnerRole, async (c) => {
  const user = c.get('user' as never) as any;
  try {
    const task_id = await triggerCeleryTask('tasks.run_rl_pipeline', {
      owner_username: user.username
    });
    
    return c.json({
      message: "RL pipeline manually triggered in background.",
      task_id: task_id
    });
  } catch (error: any) {
    return c.json({ error: error.message }, 500);
  }
});
