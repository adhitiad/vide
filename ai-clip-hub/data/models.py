from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class TopicMemory(Base):
    __tablename__ = 'topic_memory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    times_chosen = Column(Integer, default=0, nullable=False)
    score = Column(Float, default=0.0, nullable=False)

    def __repr__(self):
        return f"<TopicMemory(name='{self.name}', score={self.score}, times_chosen={self.times_chosen})>"
