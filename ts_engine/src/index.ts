import { OpenAPIHono } from '@hono/zod-openapi';
import { apiReference } from '@scalar/hono-api-reference';
import { routeApp } from './api/routes';
import { authApp } from './api/auth';
import { dashboardApp } from './api/dashboard';
import { systemApp } from './api/system';
import { wsApp, bunWebsocket } from './api/websockets';
import { connectToDatabase } from './db/mongo';
import { config } from 'dotenv';
import path from 'path';

// Load .env relative to the root project directory
config({ path: path.resolve(__dirname, '../../../.env') });

console.log("==============================================");
console.log("   🚀 AI-CLIP-HUB HONO ENGINE (BUN) 🚀      ");
console.log("==============================================");

// Initialize DB Connection
await connectToDatabase();

const app = new OpenAPIHono();

// ---- API SETUP ---- //

// Openapi registry doc setup
app.doc('/doc', {
  openapi: '3.0.0',
  info: {
    version: '1.0.0',
    title: 'AI-Clip-Hub Dashboard API (Hono Native)',
  },
});

// Swagger UI / Scalar Reference setup
app.get(
  '/swagger',
  apiReference({
    theme: 'kepler',
    // Scalar mengupdate typenya di versi baru, sehingga `url` dan `content` 
    // dinaikkan ke root level dan 'spec' tidak lagi terdefinisi di TypeScript.
    url: '/doc',
  })
);

// Mount API routes
app.route('/api/task', routeApp); // Refactored original /api/task/start to generic /api/task space
app.route('/api/auth', authApp);
app.route('/api', dashboardApp);
app.route('/api/system', systemApp);
app.route('/ws', wsApp);

// Basic health check route
app.get('/', (c) => {
  return c.text('AI-Clip-Hub Hono Engine is Running! Check /swagger for documentation.');
});

// Start the Bun server on port 8080
export default {
  port: 8080,
  fetch: app.fetch,
  websocket: bunWebsocket,
};

console.log('✅ Server berjalan di http://localhost:8080');
console.log('🔗 Swagger UI tersedia di http://localhost:8080/swagger');
