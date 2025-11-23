"""
Pipelines package.

데이터 수집부터 임베딩까지의 전체 파이프라인을 정의합니다.
"""

from .data_pipeline import (
    data_etl_pipeline,
    end_to_end_data_pipeline,
)
from .crawl import crawl_all, crawl_calendar, crawl_google_calendar, crawl_notion
from .preprocess import run_preprocessing
from .embed import run_embedding

__all__ = [
    # Main pipelines
    "data_etl_pipeline",
    "end_to_end_data_pipeline",
    # Crawl functions
    "crawl_all",
    "crawl_calendar",
    "crawl_google_calendar",
    "crawl_notion",
    # Preprocess
    "run_preprocessing",
    # Embedding
    "run_embedding",
]
