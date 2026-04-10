import { Redis } from 'ioredis';
import { z } from 'zod';

// Skema untuk data video viral
export const VideoResultSchema = z.object({
  Platform: z.string(),
  VideoURL: z.string().url(),
  Title: z.string(),
  Views: z.number().int().nonnegative(),
  Published: z.string().datetime(), // ISO 8601 string
});

export type VideoResult = z.infer<typeof VideoResultSchema>;

// Inisialisasi koneksi Redis
const redisHost = process.env.REDIS_HOST || 'localhost';
const redisPort = parseInt(process.env.REDIS_PORT || '6379', 10);
const redisPassword = process.env.REDIS_PASSWORD || undefined;

export const redisClient = new Redis({
  host: redisHost,
  port: redisPort,
  password: redisPassword,
});

redisClient.on('connect', () => {
  console.log(`✅ Terhubung ke Redis (${redisHost}:${redisPort}) via Bun`);
});

redisClient.on('error', (err) => {
  console.error(`❌ Redis Error: ${err}`);
});

/**
 * Encode a message as base64
 */
function encodeBase64(data: any): string {
  const jsonStr = JSON.stringify(data);
  return Buffer.from(jsonStr).toString('base64');
}

/**
 * Trigger generic Python Task in Celery via Redis LPUSH
 */
export async function triggerCeleryTask(taskName: string, kwargs: Record<string, any> = {}, args: any[] = []) {
  const taskID = `ts-job-${Date.now()}`;

  // Format Body Celery v2: [args, kwargs, embed_metadata]
  const embedMetadata = {
    callbacks: null,
    errbacks: null,
    chain: null,
    chord: null,
  };

  const bodyData = [args, kwargs, embedMetadata];
  const bodyBase64 = encodeBase64(bodyData);

  const message = {
    body: bodyBase64,
    headers: {
      lang: 'py',
      task: taskName,
      id: taskID,
      root_id: taskID,
      parent_id: null,
      group: null,
      origin: 'ts-engine',
    },
    properties: {
      correlation_id: taskID,
      reply_to: '',
      delivery_mode: 2,
      delivery_tag: taskID,
      priority: 0,
      body_encoding: 'base64',
      delivery_info: {
        exchange: '',
        routing_key: 'celery',
      },
    },
    'content-type': 'application/json',
    'content-encoding': 'utf-8',
  };

  try {
    const messageJSON = JSON.stringify(message);
    await redisClient.lpush('celery', messageJSON);
    console.log(`🚀 Task '${taskName}' dikirim ke Python Worker. (ID: ${taskID})`);
    return taskID;
  } catch (error) {
    console.error(`⚠️ Gagal mengirim task ke Redis:`, error);
    throw error;
  }
}

/**
 * Trigger Python Task in Celery via Redis LPUSH (Legacy compatible)
 */
export async function triggerPythonTask(
  videoPath: string,
  sourceURL: string,
  title: string,
  platform: string
) {
  return triggerCeleryTask('tasks.process_video_from_go', {}, [videoPath, sourceURL, title, platform]);
}
