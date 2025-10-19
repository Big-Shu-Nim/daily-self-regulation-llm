from abc import ABC
from typing import Optional
from datetime import datetime
from pydantic import UUID4, Field

from .base import NoSQLBaseDocument
from .types import DataCategory


class UserDocument(NoSQLBaseDocument):
    first_name: str
    last_name: str

    class Settings:
        name = "users"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Document(NoSQLBaseDocument, ABC):
    content: dict
    platform: str
    author_id: UUID4 = Field(alias="author_id")
    author_full_name: str = Field(alias="author_full_name")


class RepositoryDocument(Document):
    name: str
    link: str

    class Settings:
        name = DataCategory.REPOSITORIES


class PostDocument(Document):
    image: Optional[str] = None
    link: str | None = None

    class Settings:
        name = DataCategory.POSTS


class ArticleDocument(Document):
    link: str

    class Settings:
        name = DataCategory.ARTICLES

class NaverPostDocument(Document):
    content: dict
    naver_blog_id: str
    naver_log_no: str
    link: str
    published_at: str
    platform: str = "naver_blog"
    class Settings:
        name = "naver_posts"

        
class NotionPageDocument(Document):
    """
    Represents a single page from Notion, including modification time for sync.
    """
    title: str
    content: str  # Changed from dict to str to hold markdown
    ancestors: list = Field(default_factory=list)
    children: list = Field(default_factory=list)
    grandchildren: list = Field(default_factory=list)
    notion_page_id: str
    url: str
    last_edited_time: datetime
    created_time: datetime
    platform: str = "notion"

    class Settings:
        name = "notion_pages"
        
class ProcessedFileDocument(NoSQLBaseDocument):
    """
    Tracks files that have already been processed to prevent duplicate processing.
    """
    file_path: str
    file_hash: str  # SHA256 hash of the file content
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "success"

    class Settings:
        name = "processed_files"
    
class CalendarDocument(Document):
    """
    Represents a calendar event with structured content.
    The 'content' field holds key information like title and notes.
    """
    # content 필드를 dict 타입으로 명시합니다.
    content: dict

    # 나머지 Calendar 고유 필드는 그대로 둡니다.
    start_datetime: datetime
    end_datetime: datetime
    calendar_name: str
    duration_minutes: int
    # event_notes 필드는 이제 content 안으로 들어가므로 제거합니다.
    
    platform: str | None = "icloud_calendar"

    class Settings:
        name = "calendar"