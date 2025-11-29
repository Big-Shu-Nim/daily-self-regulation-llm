"""
Feedback Document Models.

생성된 피드백을 MongoDB에 저장하기 위한 문서 모델입니다.
"""

from abc import ABC
from datetime import datetime
from typing import Optional

from pydantic import Field

from .base import NoSQLBaseDocument


class FeedbackDocument(NoSQLBaseDocument, ABC):
    """
    피드백 문서 기본 클래스.

    모든 피드백 타입(daily, weekly, monthly)의 공통 필드를 정의합니다.
    """

    # 피드백 타입
    feedback_type: str  # "daily", "weekly", "monthly"

    # 대상 기간
    target_date: str  # YYYY-MM-DD (daily/weekly start) or YYYY-MM (monthly)

    # 생성된 피드백 내용
    content: str  # 마크다운 형식

    # 생성 메타데이터
    model_used: str  # 사용한 LLM 모델 (예: "gpt-4o-mini")
    temperature: float  # LLM temperature
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # 작성자 정보 (선택적)
    author_full_name: Optional[str] = None

    # 통계 (선택적, 생성 시 계산된 통계)
    stats: Optional[dict] = None
    # 예시:
    # {
    #     "total_docs": 150,
    #     "by_platform": {"calendar": 100, "notion": 30, "naver_blog": 20},
    #     "date_range": {"start": "2025-11-04", "end": "2025-11-06"}
    # }


class DailyFeedbackDocument(FeedbackDocument):
    """
    일일 피드백 문서.

    3일 윈도우 기반 일일 피드백을 저장합니다.
    """

    feedback_type: str = "daily"

    # 일일 피드백 전용 필드
    prompt_style: str = "original"  # original, coach, scientist, etc.

    # 컨텍스트 윈도우 설정
    include_previous: bool = True
    include_next: bool = True

    class Settings:
        name = "daily_feedback"
        indexes = [
            [("target_date", 1), ("author_full_name", 1)],  # 날짜 + 작성자 검색용
            [("generated_at", -1)],  # 최신순 정렬용
        ]


class WeeklyFeedbackDocument(FeedbackDocument):
    """
    주간 피드백 문서.

    7일 데이터 기반 주간 피드백을 저장합니다.
    """

    feedback_type: str = "weekly"

    # 주간 피드백 전용 필드
    end_date: str  # YYYY-MM-DD (주 종료일)

    # 과거 주간 리포트 참조 여부
    included_past_reports: bool = False

    # JSON summary (structured output from LLM, if available)
    json_summary: Optional[dict] = None
    # 예시:
    # {
    #     "range": {"start": "2025-11-04", "end": "2025-11-10"},
    #     "hours": {"creator": 20.5, "learner": 15.0, ...},
    #     "patterns": {...}
    # }

    class Settings:
        name = "weekly_feedback"
        indexes = [
            [("target_date", 1), ("author_full_name", 1)],  # 주 시작일 + 작성자
            [("generated_at", -1)],
        ]


class PublicDailyFeedbackDocument(FeedbackDocument):
    """
    공개용 일일 피드백 문서.

    개인정보 보호된 공개용 피드백을 별도 컬렉션에 저장합니다.
    - 프롬프트 스타일: "public" 고정
    - 날짜 범위: 2025-11-05 ~ 2025-11-12 (샘플)
    - 개인용 피드백과 분리된 컬렉션
    """

    feedback_type: str = "daily"

    # 공개용은 "public" 프롬프트만 사용
    prompt_style: str = "public"

    # 컨텍스트 윈도우 설정
    include_previous: bool = True
    include_next: bool = True

    class Settings:
        name = "public_daily_feedback"  # 별도 컬렉션
        indexes = [
            [("target_date", 1)],  # 날짜 검색용
            [("generated_at", -1)],  # 최신순 정렬용
        ]


class PublicWeeklyFeedbackDocument(FeedbackDocument):
    """
    공개용 주간 피드백 문서.

    개인정보 보호된 공개용 주간 피드백을 별도 컬렉션에 저장합니다.
    - 프롬프트 스타일: "v2_public" 고정
    - 사전 계산 메트릭 기반
    - 개인용 피드백과 분리된 컬렉션
    """

    feedback_type: str = "weekly"

    # 주간 피드백 전용 필드
    end_date: str  # YYYY-MM-DD (주 종료일)
    prompt_style: str = "v2_public"  # 공개용은 v2_public만 사용

    # 사전 계산된 메트릭 (선택적)
    precomputed_metrics: Optional[dict] = None

    class Settings:
        name = "public_weekly_feedback"  # 별도 컬렉션
        indexes = [
            [("target_date", 1), ("end_date", 1)],  # 주 시작일/종료일 검색용
            [("generated_at", -1)],  # 최신순 정렬용
        ]


class PublicMonthlyFeedbackDocument(FeedbackDocument):
    """
    공개용 월간 피드백 문서.

    개인정보 보호된 공개용 월간 피드백을 별도 컬렉션에 저장합니다.
    - 프롬프트 스타일: "v2_public" 고정
    - 주간 V2 Public 리포트 기반 계층적 요약
    - 개인용 피드백과 분리된 컬렉션
    """

    feedback_type: str = "monthly"

    # 월간 피드백 전용 필드
    year: int
    month: int
    prompt_style: str = "v2_public"  # 공개용은 v2_public만 사용

    # 주별 V2 Public 리포트 (계층적 요약의 중간 단계)
    weekly_v2_reports: Optional[list[str]] = None

    class Settings:
        name = "public_monthly_feedback"  # 별도 컬렉션
        indexes = [
            [("year", 1), ("month", 1)],  # 년월 검색용
            [("generated_at", -1)],  # 최신순 정렬용
        ]


class MonthlyFeedbackDocument(FeedbackDocument):
    """
    월간 피드백 문서.

    계층적 요약 기반 월간 피드백을 저장합니다.
    """

    feedback_type: str = "monthly"

    # 월간 피드백 전용 필드
    year: int
    month: int

    # 주별 요약 (계층적 요약의 중간 단계)
    weekly_summaries: Optional[list[str]] = None

    class Settings:
        name = "monthly_feedback"
        indexes = [
            [("year", 1), ("month", 1), ("author_full_name", 1)],  # 년월 + 작성자
            [("generated_at", -1)],
        ]
