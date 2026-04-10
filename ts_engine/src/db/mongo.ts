import { MongoClient, Db } from 'mongodb';

const uri = process.env.MONGO_URI || "mongodb://localhost:27017/";
const dbName = process.env.MONGO_DB_NAME || "vide_db";

let client: MongoClient | null = null;
let db: Db | null = null;

export async function connectToDatabase(): Promise<{ client: MongoClient, db: Db }> {
  if (client && db) {
    return { client, db };
  }

  client = new MongoClient(uri);
  await client.connect();
  db = client.db(dbName);
  
  console.log(`✅ Berhasil terhubung ke MongoDB (Hono) - Database: ${dbName}`);
  return { client, db };
}

export function getDb(): Db {
  if (!db) {
    throw new Error('Database belum terhubung. Pastikan memanggil connectToDatabase dahulu.');
  }
  return db;
}
