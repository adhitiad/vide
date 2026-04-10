import datetime
from typing import Optional, List

class TopicMemory:
    """Model untuk menyimpan skor dan frekuensi pemilihan topik."""
    def __init__(self, name: str, times_chosen: int = 0, score: float = 0.0, _id=None):
        self._id = _id
        self.name = name
        self.times_chosen = times_chosen
        self.score = score

    @classmethod
    def from_dict(cls, data: dict):
        if not data: return None
        return cls(**data)

    def to_dict(self):
        return {
            "name": self.name,
            "times_chosen": self.times_chosen,
            "score": self.score
        }

class PublishedVideo:
    """Model untuk rekam jejak video yang sudah dipublikasikan."""
    def __init__(
        self,
        topic_name: str,
        video_url: str,
        owner_username: str,
        platform: str = "youtube",
        published_at: datetime.datetime = None,
        platform_video_id: Optional[str] = None,
        views: int = 0,
        likes: int = 0,
        comments: int = 0,
        performance_status: str = "PENDING",
        last_checked: Optional[datetime.datetime] = None,
        _id=None
    ):
        self._id = _id
        self.topic_name = topic_name
        self.video_url = video_url
        self.owner_username = owner_username
        self.platform = platform
        self.published_at = published_at or datetime.datetime.utcnow()
        self.platform_video_id = platform_video_id
        self.views = views
        self.likes = likes
        self.comments = comments
        self.performance_status = performance_status
        self.last_checked = last_checked

    @property
    def hours_since_published(self) -> float:
        now = datetime.datetime.utcnow()
        delta = now - self.published_at
        return delta.total_seconds() / 3600

    @classmethod
    def from_dict(cls, data: dict):
        if not data: return None
        return cls(**data)

    def to_dict(self):
        return {
            "topic_name": self.topic_name,
            "video_url": self.video_url,
            "owner_username": self.owner_username,
            "platform": self.platform,
            "published_at": self.published_at,
            "platform_video_id": self.platform_video_id,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "performance_status": self.performance_status,
            "last_checked": self.last_checked
        }

class UploadQueue:
    """Model untuk antrean upload video."""
    def __init__(
        self,
        video_path: str,
        title: str,
        owner_username: str,
        description: str = "",
        tags: str = "",
        topic_name: Optional[str] = None,
        platform: str = "youtube",
        status: str = "pending",
        last_error: Optional[str] = None,
        error_code: Optional[int] = None,
        retry_count: int = 0,
        max_retries: int = 3,
        published_url: Optional[str] = None,
        created_at: datetime.datetime = None,
        scheduled_at: datetime.datetime = None,
        published_at: Optional[datetime.datetime] = None,
        next_retry_at: Optional[datetime.datetime] = None,
        _id=None
    ):
        self._id = _id
        self.video_path = video_path
        self.title = title
        self.owner_username = owner_username
        self.description = description
        self.tags = tags
        self.topic_name = topic_name
        self.platform = platform
        self.status = status
        self.last_error = last_error
        self.error_code = error_code
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.published_url = published_url
        self.created_at = created_at or datetime.datetime.utcnow()
        self.scheduled_at = scheduled_at or datetime.datetime.utcnow()
        self.published_at = published_at
        self.next_retry_at = next_retry_at

    @classmethod
    def from_dict(cls, data: dict):
        if not data: return None
        return cls(**data)

    def to_dict(self):
        return {
            "video_path": self.video_path,
            "title": self.title,
            "owner_username": self.owner_username,
            "description": self.description,
            "tags": self.tags,
            "topic_name": self.topic_name,
            "platform": self.platform,
            "status": self.status,
            "last_error": self.last_error,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "published_url": self.published_url,
            "created_at": self.created_at,
            "scheduled_at": self.scheduled_at,
            "published_at": self.published_at,
            "next_retry_at": self.next_retry_at
        }
