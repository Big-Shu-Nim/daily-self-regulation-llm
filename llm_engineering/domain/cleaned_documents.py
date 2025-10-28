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
    #     "image_gridfs_ids": ["id1", "id2"]
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


class DailySynthesisDocument(CleanedDocument):
    """
    날짜별로 3개 소스(Calendar, Notion, Naver)를 LLM으로 통합한 문서.

    목적:
    - 하루 전체의 맥락 파악 (전체 시간 사용, 목표 달성도, 감정 상태)
    - 집계 가능한 구조화된 데이터 제공
    - 원본 맥락 유지 (완전 요약 X)

    예시 content:
    "날짜: 2025-10-23

    ## 시간 사용:
      - 수면: 6.5시간
      - 일/생산: 4.2시간
      - 학습/성장: 1.5시간
      - 운동: 1.5시간
      - 휴식/회복: 2.2시간

    ## 주요 활동:
      - LLM_TWIN 프로젝트 (2.8시간): 전처리 로직 작업, VSCode 느림 이슈
      - 웨이트트레이닝 (1.5시간): 눈감기로 피로 회복 전략 사용

    ## 하이라이트:
      - 감정 핑계 대지 않고 핵심 업무 집중
      - 눈 피로 관리 전략 효과 확인

    ## 도전과제:
      - VSCode 변수 실행 느림 문제
      - 전처리 결과물 완성 못함

    ## 감정 상태: 생산적이지만 약간 답답함
    맥락: 결과물이 눈에 보이지 않아 좌절감

    ## 패턴 및 인사이트:
      - 피로도 6 이상일 때 짧은 산책/휴식이 2-3점 감소 효과
      - 눈 피로 관리를 위한 '눈감기' 전략 여러 번 사용
    ..."
    """

    platform: str = "daily_synthesis"

    # LLM이 생성한 구조화 데이터 (집계 가능한 JSON)
    synthesis_data: Dict[str, Any] = Field(default_factory=dict)
    # synthesis_data 구조:
    # {
    #   "objective_data": {
    #     "time_breakdown": {"카테고리": 시간(hours)},
    #     "key_activities": [...],
    #     "fatigue_tracking": [...]
    #   },
    #   "subjective_reflection": {
    #     "highlights": [...],
    #     "challenges": [...],
    #     "emotions": {...},
    #     "self_evaluation": {...}
    #   },
    #   "goal_alignment": {
    #     "daily_goal_achievement": "X%",
    #     "weekly_goal_contribution": "...",
    #     "balance_score": {"growth": int, "happiness": int, "health": int}
    #   },
    #   "patterns_insights": [...]
    # }

    # 원본 문서 참조 (추적용)
    source_document_ids: Dict[str, List[str]] = Field(default_factory=dict)
    # {"calendar": ["id1", "id2", ...], "notion": [...], "naver": [...]}

    # Metadata 예시:
    # {
    #     "source_counts": {
    #         "calendar": 17,
    #         "notion": 2,
    #         "naver": 1
    #     },
    #     "llm_model": "gemini-1.5-pro",
    #     "synthesis_version": "1.0"
    # }

    class Settings:
        name = "daily_synthesis"



