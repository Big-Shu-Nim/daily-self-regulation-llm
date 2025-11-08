"""
In-Context Feedback Generation Services.

이 모듈은 cleaned documents를 in-context로 로드하여 피드백을 생성하는 서비스들을 제공합니다.

서비스 타입:
- Daily: 3일 윈도우 (전날, 당일, 다음날)
- Weekly: 7일 데이터
- Monthly: 30일 데이터 (계층적 요약)

주요 차이점 (RAG와의 비교):
- RAG: 임베딩 → 검색 → 상위 N개 문서 사용
- In-Context: MongoDB 직접 쿼리 → 날짜 범위 내 모든 문서 사용
"""

from .base import BaseFeedbackGenerator
from .document_loader import DocumentLoader
from .daily.generator import DailyFeedbackGenerator
from .weekly.generator import WeeklyFeedbackGenerator
from .monthly.generator import MonthlyFeedbackGenerator

__all__ = [
    "BaseFeedbackGenerator",
    "DocumentLoader",
    "DailyFeedbackGenerator",
    "WeeklyFeedbackGenerator",
    "MonthlyFeedbackGenerator",
]
