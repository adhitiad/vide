import { OpenAPIHono, createRoute, z } from '@hono/zod-openapi';
import { DiscoveryCoordinator, GenericScraper } from '../scraper/coordinator';
import { triggerPythonTask, VideoResultSchema } from '../queue/celery';

export const routeApp = new OpenAPIHono();

// Schemas
const StartTaskQuerySchema = z.object({
  query: z.string().openapi({
    example: 'trending ai tools 2024',
    description: 'The search query for scraping videos',
  }),
});

const TaskStatusSchema = z.object({
  success: z.boolean().openapi({ example: true }),
  message: z.string().openapi({ example: 'Task scheduled successfully' }),
  results: z.array(VideoResultSchema).optional(),
});

// Route Definitions
const startTaskRoute = createRoute({
  method: 'post',
  path: '/api/task/start',
  tags: ['Tasks'],
  summary: 'Start Video Processing Task',
  description: 'Triggers the scraper to find videos and delegates the processing to Python Celery Worker via Redis.',
  request: {
    query: StartTaskQuerySchema,
  },
  responses: {
    200: {
      description: 'Tasks scheduled correctly',
      content: {
        'application/json': {
          schema: TaskStatusSchema,
        },
      },
    },
    500: {
      description: 'Server error',
      content: {
        'application/json': {
          schema: z.object({ error: z.string() }),
        },
      },
    },
  },
});

// Register Handlers
routeApp.openapi(startTaskRoute, async (c) => {
  const { query } = c.req.valid('query');

  try {
    const coordinator = new DiscoveryCoordinator([
      new GenericScraper('YouTube'),
      new GenericScraper('TikTok'),
      new GenericScraper('Instagram'),
    ]);

    const viralVideos = await coordinator.runAll(query);

    if (viralVideos.length === 0) {
      return c.json({ success: false, message: 'Tidak ada video yang ditemukan.' }, 200);
    }

    // Trigger Python task for the first video as an example
    const target = viralVideos[0];
    const mockAbsPath = 'f:/code/vide/tmp/viral_source.mp4'; // Mocked location after download

    console.log(`🤖 Mendelegasikan tugas ke Python AI Worker untuk video: ${target.Title}`);
    await triggerPythonTask(mockAbsPath, target.VideoURL, target.Title, target.Platform);

    return c.json({
      success: true,
      message: 'Task successfully sent to Celery queue.',
      results: viralVideos,
    }, 200);
  } catch (error: any) {
    console.error('Error starting task:', error);
    return c.json({ error: error.message || 'Internal server error' }, 500);
  }
});
