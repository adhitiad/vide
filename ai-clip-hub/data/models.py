from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

class TopicMemory(Base):
    __tablename__ = 'topic_memory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    times_chosen = Column(Integer, default=0, nullable=False)
    score = Column(Float, default=0.0, nullable=False)

    # Relationship ke PublishedVideo
    videos = relationship("PublishedVideo", back_populates="topic")

    def __repr__(self):
        return f"<TopicMemory(name='{self.name}', score={self.score}, times_chosen={self.times_chosen})>"

class PublishedVideo(Base):
    __tablename__ = 'published_video'

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(String(255), ForeignKey('topic_memory.name'), nullable=False)
    video_url = Column(String(255), nullable=False)
    published_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    views = Column(Integer, default=0, nullable=False)

    # Relationship kembali ke TopicMemory
    topic = relationship("TopicMemory", back_populates="videos")

    def __repr__(self):
        return f"<PublishedVideo(topic_name='{self.topic_name}', url='{self.video_url}', views={self.views})>"
