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
    # content 필드를 dict 타입으로 명시합니다.
    content: dict

    # 나머지 Calendar 고유 필드는 그대로 둡니다.
    start_datetime: datetime
    end_datetime: datetime
    calendar_name: str
    duration_minutes: int
    

    platform: str | None = "icloud_calendar"

    class Settings:
        name = DataCategory.CALENDAR


class DailySummaryDocument(NoSQLBaseDocument):
    """
    일일 요약 Document (Gemini로 생성된 요약)
    """
    ref_date: str  # YYYY-MM-DD
    author_id: UUID4
    author_full_name: str

    # Gemini 생성 요약
    summary: str

    # 생성 시간
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 요약 생성에 사용된 데이터 참조
    source_calendar_count: int = 0
    source_diary_count: int = 0
    source_naver_count: int = 0

    class Settings:
        name = "daily_summaries"


class DailyTimelineDocument(NoSQLBaseDocument):
    """
    일일 타임라인 통합 Document (대시보드용 캐시)

    원본 데이터는 각 Collection에 유지하고,
    이 Document는 빠른 조회를 위한 집계 뷰 역할
    """
    ref_date: str  # YYYY-MM-DD
    author_id: UUID4
    author_full_name: str

    # 원본 데이터 참조 (ID만 저장)
    calendar_event_ids: list[str] = Field(default_factory=list)
    notion_page_ids: list[str] = Field(default_factory=list)
    naver_post_ids: list[str] = Field(default_factory=list)

    # 집계 데이터 (캐시)
    total_events: int = 0
    total_duration_minutes: int = 0

    # Mode별 시간 (분 단위)
    time_by_mode: dict = Field(default_factory=dict)
    # {"Creator Mode": 120, "Learner Mode": 180, ...}

    # Category별 시간 (분 단위)
    time_by_category: dict = Field(default_factory=dict)
    # {"학습/성장": 180, "수면": 420, ...}

    # 활성 프로젝트 목록
    active_projects: list[str] = Field(default_factory=list)
    # ["장비 세팅", "MCP 학습", ...]

    # 일일 요약 ID 참조
    summary_id: UUID4 | None = None

    # 메타 정보
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "daily_timelines"