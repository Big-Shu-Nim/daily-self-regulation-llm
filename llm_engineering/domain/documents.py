from abc import ABC
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




class NaverPostDocument(Document):
    content: dict
    naver_blog_id: str
    naver_log_no: str
    link: str
    published_at: str
    platform: str = "naver_blog"
    class Settings:
        name = DataCategory.NAVER_POSTS 

        
class NotionPageDocument(Document):
    """
    Represents a single page from Notion, including modification time for sync.
    """
    title: str
    content: str  # Changed from dict to str to hold markdown
    ancestors: list = Field(default_factory=list)
    children: list = Field(default_factory=list)
    grandchildren: list = Field(default_factory=list)
    image_gridfs_ids: list[str] | None = None
    notion_page_id: str
    url: str
    last_edited_time: datetime
    created_time: datetime
    properties: dict = Field(default_factory=dict)  # Notion page properties (데이터베이스 필드 값)
    platform: str = "notion"

    class Settings:
        name = DataCategory.NOTION_PAGES
        
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
    # content 필드를 dict 타입으로 명시
    content: dict

    # 나머지 Calendar 고유 필드
    start_datetime: datetime
    end_datetime: datetime
    calendar_name: str
    sub_category: str | None = None
    duration_minutes: int


    platform: str | None = "icloud_calendar"

    class Settings:
        name = DataCategory.CALENDAR


class GoogleCalendarDocument(Document):
    """
    Represents a Google Calendar event retrieved via API.
    Similar to CalendarDocument but uses Google Calendar API.
    """
    content: dict  # {"title": str, "notes": str}

    # Google Calendar specific fields
    start_datetime: datetime
    end_datetime: datetime
    calendar_name: str
    sub_category: str | None = None
    duration_minutes: int

    # Google Calendar API specific
    google_event_id: str  # Google Calendar event ID
    google_calendar_id: str  # Google Calendar ID

    # Sync metadata
    last_synced_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = False  # Soft delete flag

    platform: str = "google_calendar"

    class Settings:
        name = DataCategory.GOOGLE_CALENDAR

