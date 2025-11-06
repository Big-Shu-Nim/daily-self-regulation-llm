"""
Cleaned document models for embedding and RAG.

이 모델들은 전처리(preprocessing) 후 임베딩 전 단계의 문서를 표현합니다.
- content: 임베딩할 실제 텍스트 (가장 중요!)
- metadata: 필터링/검색에 사용할 구조화된 메타데이터
"""

from abc import ABC
from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import UUID4, Field

from .base import NoSQLBaseDocument
from .types import DataCategory


class CleanedDocument(NoSQLBaseDocument, ABC):
    """
    임베딩을 위한 cleaned document의 base class.

    핵심 원칙:
    - content: 자연어 텍스트로 변환된 임베딩 대상 (LLM이 이해할 수 있는 형태)
    - metadata: 필터링/검색에 필요한 구조화된 정보
    - ref_date: 시간 기반 필터링의 핵심
    """

    # 원본 문서 ID (추적용)
    original_id: UUID4

    # 임베딩할 텍스트 (자연어 형태)
    content: str

    # 참조 날짜 (일일 회고의 기준이 되는 날짜)
    ref_date: str  # YYYY-MM-DD

    # 플랫폼/데이터 소스
    platform: str

    # 문서 타입/카테고리
    doc_type: str

    # 작성자 정보
    author_id: UUID4
    author_full_name: str

    # 유효성 플래그 (임베딩 대상 여부)
    is_valid: bool = True

    # 추가 메타데이터 (각 소스별로 다름)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # 전처리 시간
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class CleanedCalendarDocument(CleanedDocument):
    """
    Calendar 이벤트를 자연어로 변환한 문서.

    예시 content:
    "2024년 1월 15일 월요일, 오전 9시부터 11시까지 2시간 동안 '프로젝트 개발' 활동을 했습니다.
    카테고리: 개인개발. 메모: API 설계 및 데이터베이스 스키마 작성 완료."
    """

    platform: str = "calendar"

    # Calendar 특화 메타데이터
    # metadata 예시:
    # {
    #     "start_datetime": "2024-01-15T09:00:00",
    #     "end_datetime": "2024-01-15T11:00:00",
    #     "duration_minutes": 120,
    #     "calendar_name": "개인",
    #     "category": "개인개발",
    #     "event_name": "프로젝트 개발",
    #     "notes": "API 설계 및 데이터베이스 스키마 작성 완료",
    #     "is_sleep": false
    # }

    class Settings:
        name = "cleaned_calendar"
        category = DataCategory.CALENDAR


class CleanedNotionDocument(CleanedDocument):
    """
    Notion 페이지 문서.

    content는 이미 마크다운 형태의 텍스트이므로 그대로 사용 가능.
    단, 제목과 계층 정보를 추가하여 맥락 제공.

    예시 content:
    "제목: 2024년 1월 15일 업무 일지
    경로: 일일업무정리 → 2024년 1월 → 2024년 1월 15일

    [원본 마크다운 내용]
    - 오전: API 개발
    - 오후: 회의 참석
    ..."
    """

    platform: str = "notion"

    # Notion 특화 메타데이터
    # metadata 예시:
    # {
    #     "notion_page_id": "abc-123-def",
    #     "title": "2024년 1월 15일 업무 일지",
    #     "url": "https://notion.so/...",
    #     "ancestor_chain": "일일업무정리 → 2024년 1월 → ...",
    #     "created_time": "2024-01-15T09:00:00",
    #     "last_edited_time": "2024-01-15T18:00:00",
    #     "properties": {...},  # Notion 데이터베이스 속성 -> 삭제예정
    #     "has_images": true,
    #     "image_gridfs_ids": ["id1", "id2"],
    #     # Weekly report 전용 필드 (doc_type == 'weekly_report'인 경우만)
    #     "week_start_date": "2024-09-23",  # 주간 범위 시작일
    #     "week_end_date": "2024-09-29"     # 주간 범위 종료일
    # }

    class Settings:
        name = "cleaned_notion"


class CleanedNaverDocument(CleanedDocument):
    """
    Naver 블로그 포스트 문서.

    예시 content:
    "제목: 20240115_일일 회고
    발행일: 2024년 1월 15일

    [본문]
    오늘은 프로젝트 개발에 집중했다.
    API 설계를 완료했고, 내일은 테스트 코드를 작성할 예정이다.
    ..."
    """

    platform: str = "naver_blog"

    # Naver 특화 메타데이터
    # metadata 예시:
    # {
    #     "naver_blog_id": "my_blog",
    #     "naver_log_no": "123456",
    #     "title": "20240115_일일 회고",
    #     "link": "https://blog.naver.com/...",
    #     "published_at": "2024. 1. 15. 21:30",
    #     "category": "일일피드백",
    #     "post_url": "https://..."
    # }

    class Settings:
        name = "cleaned_naver"





