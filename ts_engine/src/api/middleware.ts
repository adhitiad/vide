import type { Context, Next } from 'hono';
import jwt from 'jsonwebtoken';
import { getDb } from '../db/mongo';

const SECRET_KEY = process.env.JWT_SECRET_KEY || "your_fallback_secret_key_change_this";

export async function requireAuth(c: Context, next: Next) {
  const authHeader = c.req.header('Authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return c.json({ detail: "Token tidak valid atau sudah kedaluwarsa" }, 401);
  }

  const token = authHeader.split(' ')[1];
  try {
    const decoded: any = jwt.verify(token, SECRET_KEY);
    const username = decoded.sub;

    if (!username) {
      return c.json({ detail: "Token tidak valid" }, 401);
    }

    const db = getDb();
    const user = await db.collection('users').findOne({ username });

    if (!user) {
      return c.json({ detail: "User tidak ditemukan" }, 401);
    }

    if (user.is_active === false) {
      return c.json({ detail: "Akun Anda telah dinonaktifkan." }, 403);
    }

    // Set user di context
    c.set('user', user);
    await next();
  } catch (error: any) {
    if (error.name === 'TokenExpiredError') {
      return c.json({ detail: "Token kedaluwarsa. Silakan login lagi." }, 401);
    }
    return c.json({ detail: "Token tidak valid" }, 401);
  }
}

export async function requireOwnerRole(c: Context, next: Next) {
  // requires requireAuth to be called first
  const user = c.get('user');
  if (!user || user.role !== 'owner') {
    return c.json({ detail: "Akses Ditolak! Endpoint ini khusus untuk Owner." }, 403);
  }
  await next();
}
