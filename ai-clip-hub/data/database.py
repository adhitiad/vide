import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .models import Base, TopicMemory
from logger import logger

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_memory.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Inisialisasi Database Engine dan Session Maker
try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

    # Buat tabel jika belum ada
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database SQLite berhasil diinisialisasi.")
except Exception as e:
    logger.error(f"❌ Gagal inisialisasi Database SQLite: {e}")
    raise

def get_db_session():
    """Fungsi pembantu untuk mendapatkan sesi DB"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_default_topics():
    """Menginisialisasi topik default jika db kosong"""
    session = SessionLocal()
    try:
        if session.query(TopicMemory).count() == 0:
            default_topics = [
                TopicMemory(name="bisnis online", score=10.0),
                TopicMemory(name="investasi pemula", score=10.0),
                TopicMemory(name="motivasi sukses", score=10.0),
                TopicMemory(name="teknologi terbaru", score=10.0),
                TopicMemory(name="AI tools 2024", score=10.0)
            ]
            session.add_all(default_topics)
            session.commit()
            logger.info("✅ Menambahkan topik default ke SQLite.")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Gagal menambahkan topik default: {e}")
    finally:
        session.close()

# Panggil fungsi inisialisasi awal
init_default_topics()
