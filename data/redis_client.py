import redis
import json
import os
from dotenv import load_dotenv
from logger import logger

from data.database import SessionLocal
from data.models import TopicMemory
import time

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
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            self._use_redis = False
            logger.warning(
                "🔴 Redis tidak ditemukan/mati. Fallback otomatis menggunakan SQLite!"
            )

    def set_topic_score(self, topic_name: str, score: float, times_chosen: int = None):
        """Menyimpan atau mengupdate skor topik (Redis -> SQLite)"""
        # 1. Update ke SQLite (sebagai persistent storage)
        session = SessionLocal()
        try:
            topic = (
                session.query(TopicMemory)
                .filter(TopicMemory.name == topic_name)
                .first()
            )
            if topic:
                topic.score = score
                if times_chosen is not None:
                    topic.times_chosen = times_chosen
            else:
                topic = TopicMemory(
                    name=topic_name, score=score, times_chosen=times_chosen or 1
                )
                session.add(topic)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Gagal update SQLite untuk topik '{topic_name}': {e}")
        finally:
            session.close()

        # 2. Update ke Redis (jika aktif)
        if self._use_redis:
            try:
                data = {
                    "score": score,
                    "times_chosen": times_chosen or 1,
                    "last_updated": int(time.time()),
                }
                self._client.set(f"topic:{topic_name}", json.dumps(data))
                # logger.info(f"💾 Disimpan ke Redis: {topic_name} -> {score}")
            except Exception as e:
                logger.warning(f"⚠️ Gagal menyimpan ke Redis: {e}")

    def get_topic_score(self, topic_name: str) -> dict:
        """Mengambil skor topik (Prioritas: Redis -> SQLite)"""
        if self._use_redis:
            try:
                data_str = self._client.get(f"topic:{topic_name}")
                if data_str:
                    return json.loads(data_str)
            except Exception as e:
                logger.warning(f"⚠️ Gagal membaca Redis: {e}. Fallback SQLite.")

        # Fallback ke SQLite
        session = SessionLocal()
        try:
            topic = (
                session.query(TopicMemory)
                .filter(TopicMemory.name == topic_name)
                .first()
            )
            if topic:
                return {"score": topic.score, "times_chosen": topic.times_chosen}
            return {"score": 0.0, "times_chosen": 0}
        except Exception as e:
            logger.error(f"❌ Gagal membaca SQLite: {e}")
            return {"score": 0.0, "times_chosen": 0}
        finally:
            session.close()

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
                # Kunci maksimal (misal 1 jam) agar tidak menyangkut jika worker terputus/crash
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
        """Mendapatkan semua topik dari SQLite untuk Leaderboard"""
        session = SessionLocal()
        try:
            topics = session.query(TopicMemory).order_by(TopicMemory.score.desc()).all()
            result = [
                {"name": t.name, "score": t.score, "times_chosen": t.times_chosen}
                for t in topics
            ]
            return result
        except Exception as e:
            logger.error(f"❌ Gagal mengambil semua topik dari SQLite: {e}")
            return []
        finally:
            session.close()


redis_client = RedisManager()
