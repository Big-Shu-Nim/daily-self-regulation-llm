"""
Preprocessing module for cleaning and preparing data for embedding.

이 모듈은 다양한 데이터 소스(Calendar, Notion, Naver)를 전처리하여
임베딩에 적합한 형태로 변환합니다.

사용 예시:
    from llm_engineering.application.preprocessing import PreprocessorDispatcher

    # Dispatcher 생성
    dispatcher = PreprocessorDispatcher()

    # 개별 전처리
    calendar_cleaned = dispatcher.preprocess(df_calendar, "calendar")
    notion_cleaned = dispatcher.preprocess(df_notion, "notion")
    naver_cleaned = dispatcher.preprocess(df_naver, "naver", filter_categories=["일일피드백"])

    # 일괄 전처리
    all_cleaned = dispatcher.preprocess_all({
        "calendar": df_calendar,
        "notion": df_notion,
        "naver": df_naver
    })
"""

from .base import BasePreprocessor
from .calendar import CalendarPreprocessor
from .notion import NotionPreprocessor
from .naver import NaverPreprocessor
from .synthesizer import DailySynthesizer
from .dispatcher import PreprocessorDispatcher, PREPROCESSOR_REGISTRY

__all__ = [
    "BasePreprocessor",
    "CalendarPreprocessor",
    "NotionPreprocessor",
    "NaverPreprocessor",
    "DailySynthesizer",
    "PreprocessorDispatcher",
    "PREPROCESSOR_REGISTRY",
]
