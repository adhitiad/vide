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

# Fungsi inisialisasi topik default / hardcode DIHAPUS sesuai permintaan.
# Agen AI akan sepenuhnya meriset dan membangun database dari 0 berdasarkan Google News.
