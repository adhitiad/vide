import redis
import json
import os
import time
from dotenv import load_dotenv
from logger import logger

from data.mongodb_client import db

load_dotenv()


class RedisManager:
    _instance = None
    _client = None
    _use_redis = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
            cls._instance._initialize_connection()
        return cls._instance

    def _initialize_connection(self):
        try:
            # Mencoba connect Redis lokal tanpa password
            self._client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                username=os.getenv("REDIS_USERNAME"),
                password=os.getenv("REDIS_PASSWORD"),
                db=0,
                decode_responses=True,
                socket_timeout=2,
            )
            # Uji koneksi
            self._client.ping()
            self._use_redis = True
            logger.info("🟢 Redis terhubung! Memori cache aktif.")
        except (redis.ConnectionError, redis.TimeoutError):
            self._use_redis = False
            logger.warning(
                "🔴 Redis tidak ditemukan/mati. Fallback otomatis menggunakan MongoDB!"
            )

    def set_topic_score(self, topic_name: str, score: float, times_chosen: int = None):
        """Menyimpan atau mengupdate skor topik (Redis -> MongoDB)"""
        # 1. Update ke MongoDB
        try:
            update_data = {"score": score}
            if times_chosen is not None:
                update_data["times_chosen"] = times_chosen
            
            # Gunakan ops tunggal untuk menghindari konflik $set/$setOnInsert pada field yang sama
            db.topic_memory.update_one(
                {"name": topic_name},
                {
                    "$set": update_data,
                    "$setOnInsert": {"created_at": int(time.time())}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"❌ Gagal update MongoDB untuk topik '{topic_name}': {e}")

        # 2. Update ke Redis (jika aktif)
        if self._use_redis and self._client:
            try:
                data = {
                    "score": score,
                    "times_chosen": times_chosen or 1,
                    "last_updated": int(time.time()),
                }
                self._client.set(f"topic:{topic_name}", json.dumps(data))
            except Exception as e:
                logger.warning(f"⚠️ Gagal menyimpan ke Redis: {e}")

    def get_topic_score(self, topic_name: str) -> dict:
        """Mengambil skor topik (Prioritas: Redis -> MongoDB)"""
        if self._use_redis and self._client:
            try:
                data_str = self._client.get(f"topic:{topic_name}")
                if data_str:
                    return json.loads(str(data_str))
            except Exception as e:
                logger.warning(f"⚠️ Gagal membaca Redis: {e}. Fallback MongoDB.")

        # Fallback ke MongoDB
        try:
            topic = db.topic_memory.find_one({"name": topic_name})
            if topic:
                return {
                    "score": topic.get("score", 0.0),
                    "times_chosen": topic.get("times_chosen", 0)
                }
            return {"score": 0.0, "times_chosen": 0}
        except Exception as e:
            logger.error(f"❌ Gagal membaca MongoDB: {e}")
            return {"score": 0.0, "times_chosen": 0}

    def is_task_active(self, topic_name: str) -> bool:
        """Mengecek apakah topik sedang diproses (terkunci) oleh worker lain"""
        if self._use_redis and self._client:
            try:
                return bool(self._client.exists(f"active_task:{topic_name}"))
            except Exception as e:
                logger.warning(f"⚠️ Gagal mengecek status tugas di Redis: {e}")
        return False

    def add_active_task(self, topic_name: str, expiry_seconds: int = 3600):
        """Menambahkan topik ke daftar tugas aktif (dikunci) dengan waktu kadaluarsa"""
        if self._use_redis and self._client:
            try:
                self._client.setex(
                    f"active_task:{topic_name}", expiry_seconds, "locked"
                )
            except Exception as e:
                logger.warning(f"⚠️ Gagal menambahkan kunci tugas di Redis: {e}")

    def remove_active_task(self, topic_name: str):
        """Menghapus topik dari daftar tugas aktif (membuka kunci)"""
        if self._use_redis and self._client:
            try:
                self._client.delete(f"active_task:{topic_name}")
            except Exception as e:
                logger.warning(f"⚠️ Gagal menghapus kunci tugas di Redis: {e}")

    def get_all_topics(self):
        """Mendapatkan semua topik dari MongoDB untuk Leaderboard"""
        try:
            topics = list(db.topic_memory.find().sort("score", -1))
            return [
                {
                    "name": t["name"],
                    "score": t["score"],
                    "times_chosen": t.get("times_chosen", 0)
                }
                for t in topics
            ]
        except Exception as e:
            logger.error(f"❌ Gagal mengambil semua topik dari MongoDB: {e}")
            return []


redis_client = RedisManager()
