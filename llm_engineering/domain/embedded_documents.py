"""
Embedded document models for Qdrant vector storage.

CleanedDocuments를 임베딩하여 Qdrant에 저장하는 모델들입니다.
- embedding: 벡터 임베딩 (필수)
- content: 임베딩된 원본 텍스트
- metadata: 검색 필터링용 메타데이터
"""

from abc import ABC
from typing import Optional, Dict, Any

from pydantic import UUID4, Field

from .base import VectorBaseDocument
from .types import DataCategory


class EmbeddedDocument(VectorBaseDocument, ABC):
    """
    임베딩된 문서의 base class.

    핵심 필드:
    - content: 임베딩된 원본 텍스트
    - embedding: 벡터 임베딩 (Qdrant 검색용)
    - original_id: CleanedDocument의 원본 ID
    - ref_date: 날짜 기반 필터링용
    """

    # 임베딩된 텍스트 (원본)
    content: str

    # 벡터 임베딩
    embedding: list[float] | None = None

    # 원본 CleanedDocument ID (추적용)
    original_id: UUID4

    # 참조 날짜 (필터링용)
    ref_date: str  # YYYY-MM-DD

    # 플랫폼/소스
    platform: str

    # 문서 타입
    doc_type: str

    # 작성자 정보
    author_id: UUID4
    author_full_name: str

    # 추가 메타데이터
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def to_context(cls, docs: list["EmbeddedDocument"]) -> str:
        """
        검색된 여러 문서를 LLM 컨텍스트 형식으로 변환합니다.

        Args:
            docs: 검색된 임베딩 문서 리스트

        Returns:
            LLM 프롬프트에 사용할 컨텍스트 문자열
        """
        context = ""
        for i, doc in enumerate(docs):
            context += f"""
            Document {i + 1}:
            Type: {doc.__class__.__name__}
            Platform: {doc.platform}
            Doc Type: {doc.doc_type}
            Date: {doc.ref_date}
            Author: {doc.author_full_name}

            Content:
            {doc.content}

            ---
            """

        return context


class EmbeddedCalendarDocument(EmbeddedDocument):
    """
    임베딩된 Calendar 문서.

    content 예시:
    "2024년 1월 15일 월요일, 오전 9시부터 11시까지 2시간 동안 '프로젝트 개발' 활동을 했습니다.
    카테고리: 개인개발. 메모: API 설계 및 데이터베이스 스키마 작성 완료."
    """

    platform: str = "calendar"

    # Calendar 특화 메타데이터는 metadata 필드에 저장
    # {
    #     "start_datetime": "2024-01-15T09:00:00",
    #     "end_datetime": "2024-01-15T11:00:00",
    #     "duration_minutes": 120,
    #     "calendar_name": "개인",
    #     "category": "개인개발",
    #     "is_sleep": false,
    #     "embedding_model_id": "text-embedding-3-small",
    #     "embedding_size": 1536
    # }

    class Config:
        name = "embedded_calendar"
        category = DataCategory.CALENDAR
        use_vector_index = True


class EmbeddedNotionDocument(EmbeddedDocument):
    """
    임베딩된 Notion 문서.

    content 예시:
    "제목: 2024년 1월 15일 업무 일지
    경로: 일일업무정리 → 2024년 1월

    [마크다운 내용]
    - 오전: API 개발
    - 오후: 회의 참석
    ..."
    """

    platform: str = "notion"

    # Notion 특화 메타데이터
    # {
    #     "notion_page_id": "abc-123-def",
    #     "title": "2024년 1월 15일 업무 일지",
    #     "url": "https://notion.so/...",
    #     "has_images": true,
    #     "embedding_model_id": "text-embedding-3-small",
    #     "embedding_size": 1536
    # }

    class Config:
        name = "embedded_notion"
        category = DataCategory.NOTION_PAGES
        use_vector_index = True


class EmbeddedNaverDocument(EmbeddedDocument):
    """
    임베딩된 Naver 블로그 문서.

    content 예시:
    "제목: 20240115_일일 회고
    발행일: 2024년 1월 15일

    [본문]
    오늘은 프로젝트 개발에 집중했다.
    API 설계를 완료했고, 내일은 테스트 코드를 작성할 예정이다.
    ..."
    """

    platform: str = "naver_blog"

    # Naver 특화 메타데이터
    # {
    #     "naver_blog_id": "my_blog",
    #     "naver_log_no": "123456",
    #     "title": "20240115_일일 회고",
    #     "link": "https://blog.naver.com/...",
    #     "category": "일일피드백",
    #     "embedding_model_id": "text-embedding-3-small",
    #     "embedding_size": 1536
    # }

    class Config:
        name = "embedded_naver"
        category = DataCategory.NAVER_POSTS
        use_vector_index = True
