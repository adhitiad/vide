import { Hono } from 'hono';
import { getDb } from '../db/mongo';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import os from 'os';

export const authApp = new Hono();

const SECRET_KEY = process.env.JWT_SECRET_KEY || "your_fallback_secret_key_change_this";
const ACCESS_TOKEN_EXPIRE_MINUTES = parseInt(process.env.JWT_ACCESS_TOKEN_EXPIRE_MINUTES || "1440");

authApp.post('/login', async (c) => {
  try {
    let username = '';
    let password = '';
    
    // Parse form-data or JSON (Hono handles it transparently but OAuth2 uses x-www-form-urlencoded)
    const contentType = c.req.header('content-type') || '';
    if (contentType.includes('application/x-www-form-urlencoded') || contentType.includes('multipart/form-data')) {
      const body = await c.req.parseBody();
      username = typeof body['username'] === 'string' ? body['username'] : '';
      password = typeof body['password'] === 'string' ? body['password'] : '';
    } else {
      const body = await c.req.json();
      username = body.username;
      password = body.password;
    }

    if (!username || !password) {
      return c.json({ detail: "Username dan password diperlukan" }, 401);
    }

    const db = getDb();
    const user = await db.collection('users').findOne({ username });

    if (!user) {
      return c.json({ detail: "Username atau Password salah" }, 401);
    }

    const hashedPassword = user.password || user.hashed_password;
    if (!hashedPassword) {
      return c.json({ detail: "Username atau Password salah" }, 401);
    }

    const isValid = await bcrypt.compare(password, hashedPassword);
    if (!isValid) {
      return c.json({ detail: "Username atau Password salah" }, 401);
    }

    const expiry = user.subscription_expiry ? new Date(user.subscription_expiry) : null;
    if (expiry && expiry.getTime() < Date.now()) {
      return c.json({ detail: "Masa berlangganan telah habis. Hubungi Admin." }, 403);
    }

    // Generate JWT
    const payload = {
      sub: user.username,
      role: user.role || 'staff',
      exp: Math.floor(Date.now() / 1000) + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    };
    
    const accessToken = jwt.sign(payload, SECRET_KEY, { algorithm: 'HS256' });

    // Logs
    const clientIp = c.req.header('CF-Connecting-IP') || c.req.header('X-Forwarded-For') || 'unknown';
    const userAgent = c.req.header('user-agent') || '';
    
    const logData = {
      username: user.username,
      role: user.role || "staff",
      ip_address: clientIp,
      device_name: "TBD - Nodejs Port", 
      location: "Unknown Location",
      login_time: new Date()
    };
    await db.collection('login_logs').insertOne(logData);

    return c.json({
      access_token: accessToken,
      token_type: "bearer",
      user_info: {
        username: user.username,
        role: user.role,
        avatar: user.avatar
      }
    });

  } catch (error: any) {
    console.error("Login Error:", error);
    return c.json({ detail: "Internal Server Error" }, 500);
  }
});
