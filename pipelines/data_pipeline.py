"""
데이터 파이프라인 모듈.

크롤링 -> 전처리 -> 임베딩의 전체 데이터 파이프라인을 제공합니다.

사용법:
    # 크롤링 + 전처리만
    python -c "from pipelines import data_etl_pipeline; data_etl_pipeline('홍', '길동')"

    # 전체 파이프라인 (크롤링 + 전처리 + 임베딩)
    python -c "from pipelines import end_to_end_data_pipeline; end_to_end_data_pipeline('홍', '길동')"
"""

from typing import Optional
from loguru import logger

from pipelines.crawl import crawl_all
from pipelines.preprocess import run_preprocessing
from pipelines.embed import run_embedding


def data_etl_pipeline(
    user_first_name: str,
    user_last_name: str,
    # 크롤링 옵션
    skip_calendar: bool = False,
    skip_google_calendar: bool = False,
    skip_notion: bool = False,
    calendar_directory: str = "llm_engineering/application/crawlers/data",
    google_calendar_id: Optional[str] = None,
    google_max_results: int = 2500,
    # 전처리 옵션
    incremental: bool = True,
    save_to_db: bool = True,
) -> dict:
    """
    데이터 ETL 파이프라인 (크롤링 + 전처리).

    MongoDB에 크롤링한 데이터를 저장하고, CleanedDocuments로 전처리합니다.

    Args:
        user_first_name: 사용자 이름
        user_last_name: 사용자 성
        skip_calendar: Calendar 크롤링 건너뛰기
        skip_google_calendar: Google Calendar 크롤링 건너뛰기
        skip_notion: Notion 크롤링 건너뛰기
        calendar_directory: Calendar 엑셀 파일 경로
        google_calendar_id: 특정 Google Calendar ID
        google_max_results: Google Calendar 최대 결과 수
        incremental: 증분 처리 여부
        save_to_db: MongoDB에 저장 여부

    Returns:
        파이프라인 실행 결과 딕셔너리
    """
    logger.info("=" * 70)
    logger.info("🚀 데이터 ETL 파이프라인 시작")
    logger.info(f"   사용자: {user_first_name} {user_last_name}")
    logger.info("=" * 70)

    results = {
        "crawl": None,
        "preprocess": None,
    }

    # Step 1: 크롤링
    logger.info("\n📌 Step 1: 데이터 크롤링")
    crawl_results = crawl_all(
        user_first_name=user_first_name,
        user_last_name=user_last_name,
        skip_calendar=skip_calendar,
        skip_google_calendar=skip_google_calendar,
        skip_notion=skip_notion,
        calendar_directory=calendar_directory,
        google_calendar_id=google_calendar_id,
        google_max_results=google_max_results,
    )
    results["crawl"] = crawl_results

    # Step 2: 전처리
    logger.info("\n📌 Step 2: 데이터 전처리")
    preprocess_results = run_preprocessing(
        incremental=incremental,
        save=save_to_db,
        verbose=True,
    )
    results["preprocess"] = preprocess_results

    # 최종 결과
    logger.info("\n" + "=" * 70)
    logger.info("✅ 데이터 ETL 파이프라인 완료")
    logger.info("=" * 70)

    return results


def end_to_end_data_pipeline(
    user_first_name: str,
    user_last_name: str,
    # 크롤링 옵션
    skip_calendar: bool = False,
    skip_google_calendar: bool = False,
    skip_notion: bool = False,
    calendar_directory: str = "llm_engineering/application/crawlers/data",
    google_calendar_id: Optional[str] = None,
    google_max_results: int = 2500,
    # 전처리 옵션
    incremental: bool = True,
    # 임베딩 옵션
    embedding_source: str = "all",
    embedding_limit: Optional[int] = None,
    skip_embedding: bool = False,
) -> dict:
    """
    End-to-End 데이터 파이프라인 (크롤링 + 전처리 + 임베딩).

    데이터 수집부터 벡터 임베딩까지 전체 파이프라인을 실행합니다.

    Args:
        user_first_name: 사용자 이름
        user_last_name: 사용자 성
        skip_calendar: Calendar 크롤링 건너뛰기
        skip_google_calendar: Google Calendar 크롤링 건너뛰기
        skip_notion: Notion 크롤링 건너뛰기
        calendar_directory: Calendar 엑셀 파일 경로
        google_calendar_id: 특정 Google Calendar ID
        google_max_results: Google Calendar 최대 결과 수
        incremental: 증분 처리 여부
        embedding_source: 임베딩할 소스 ("calendar", "notion", "naver", "all")
        embedding_limit: 각 소스별 최대 임베딩 개수
        skip_embedding: 임베딩 단계 건너뛰기

    Returns:
        파이프라인 실행 결과 딕셔너리
    """
    logger.info("=" * 70)
    logger.info("🚀 End-to-End 데이터 파이프라인 시작")
    logger.info(f"   사용자: {user_first_name} {user_last_name}")
    logger.info("=" * 70)

    results = {
        "crawl": None,
        "preprocess": None,
        "embedding": None,
    }

    # Step 1: 크롤링
    logger.info("\n📌 Step 1: 데이터 크롤링")
    crawl_results = crawl_all(
        user_first_name=user_first_name,
        user_last_name=user_last_name,
        skip_calendar=skip_calendar,
        skip_google_calendar=skip_google_calendar,
        skip_notion=skip_notion,
        calendar_directory=calendar_directory,
        google_calendar_id=google_calendar_id,
        google_max_results=google_max_results,
    )
    results["crawl"] = crawl_results

    # Step 2: 전처리
    logger.info("\n📌 Step 2: 데이터 전처리")
    preprocess_results = run_preprocessing(
        incremental=incremental,
        save=True,
        verbose=True,
    )
    results["preprocess"] = preprocess_results

    # Step 3: 임베딩
    if not skip_embedding:
        logger.info("\n📌 Step 3: 벡터 임베딩")
        embedding_results = run_embedding(
            source=embedding_source,
            limit=embedding_limit,
            dry_run=False,
        )
        results["embedding"] = embedding_results
    else:
        logger.info("\n⏭️ Step 3: 임베딩 건너뜀")

    # 최종 결과
    logger.info("\n" + "=" * 70)
    logger.info("✅ End-to-End 데이터 파이프라인 완료")
    logger.info("=" * 70)

    return results
