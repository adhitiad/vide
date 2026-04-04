from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()


class TopicMemory(Base):
    __tablename__ = "topic_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    times_chosen = Column(Integer, default=0, nullable=False)
    score = Column(Float, default=0.0, nullable=False)

    # Relationship ke PublishedVideo
    videos = relationship("PublishedVideo", back_populates="topic")

    def __repr__(self):
        return f"<TopicMemory(name='{self.name}', score={self.score}, times_chosen={self.times_chosen})>"


class PublishedVideo(Base):
    """
    Rekam jejak setiap video yang berhasil dipublikasikan.
    Kolom analytics (views, likes, comments, performance_status)
    diisi secara otomatis oleh core/analytics_tracker.py setiap jam 23:30 WIB.
    """

    __tablename__ = "published_video"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(String(255), ForeignKey("topic_memory.name"), nullable=False)
    platform = Column(String(50), nullable=False, default="youtube")
    video_url = Column(String(255), nullable=False)
    published_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # --- ID Platform (diperlukan untuk menarik statistik via API) ---
    # YouTube: video_id (contoh: "dQw4w9WgXcQ")
    # Instagram: media_code (contoh: "C1234XYZ0abc")
    platform_video_id = Column(String(255), nullable=True)

    # --- Analytics (diupdate oleh analytics_tracker.py) ---
    views = Column(Integer, default=0, nullable=False)
    likes = Column(Integer, default=0, nullable=False)
    comments = Column(Integer, default=0, nullable=False)

    # --- Status Performa ---
    # 'PENDING'   → Baru dipublish, belum cukup 24 jam untuk dievaluasi
    # 'GOOD'      → views >= 100 setelah 24 jam (performa normal)
    # 'LOW_VIEWS' → views < 100 setelah 24 jam (memicu Self-Correction & Pivot di RL)
    # 'VIRAL'     → views >= 1000 (topik ini mendapat bonus score di Redis)
    performance_status = Column(String(50), default="PENDING", nullable=False)

    # Terakhir kali statistik diambil
    last_checked = Column(DateTime, nullable=True)

    # Relationship kembali ke TopicMemory
    topic = relationship("TopicMemory", back_populates="videos")

    @property
    def hours_since_published(self) -> float:
        """Hitung berapa jam sejak video dipublish (UTC)"""
        now = datetime.datetime.utcnow()
        delta = now - self.published_at
        return delta.total_seconds() / 3600

    def __repr__(self):
        return (
            f"<PublishedVideo("
            f"topic='{self.topic_name}', "
            f"platform='{self.platform}', "
            f"views={self.views}, "
            f"status='{self.performance_status}'"
            f")>"
        )


class UploadQueue(Base):
    """
    Antrian video yang siap untuk di-upload ke YouTube.
    Status lifecycle: pending → uploading → published | failed → retrying → published | abandoned

    Video yang gagal (HttpError 400/403/quota exceeded) tidak akan membuat program crash,
    melainkan status berubah menjadi 'failed' dan akan di-retry keesokan harinya jam 14:30 WIB.
    """

    __tablename__ = "upload_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Informasi video
    video_path = Column(String(512), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    tags = Column(String(512), nullable=True, default="")  # CSV: "tag1,tag2,tag3"
    topic_name = Column(String(255), nullable=True)

    # Status tracking
    status = Column(String(50), nullable=False, default="pending")

    # Error info
    last_error = Column(Text, nullable=True)
    error_code = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # URL hasil upload
    published_url = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"<UploadQueue("
            f"id={self.id}, "
            f"title='{self.title[:30]}...', "
            f"status='{self.status}', "
            f"retry={self.retry_count}/{self.max_retries}"
            f")>"
        )
