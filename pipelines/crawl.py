"""
크롤링 모듈.

각 데이터 소스별 크롤링 함수를 제공합니다.
"""

from typing import Optional
from loguru import logger

from llm_engineering.application.crawlers.dispatcher import CrawlerDispatcher


def crawl_calendar(
    user_first_name: str,
    user_last_name: str,
    directory_path: str = "llm_engineering/application/crawlers/data"
) -> bool:
    """
    엑셀 기반 캘린더 데이터를 크롤링합니다.

    Args:
        user_first_name: 사용자 이름
        user_last_name: 사용자 성
        directory_path: 캘린더 엑셀 파일 경로

    Returns:
        성공 여부
    """
    logger.info("📅 Calendar 크롤링 시작...")

    try:
        user_info = {"first_name": user_first_name, "last_name": user_last_name}
        dispatcher = CrawlerDispatcher()
        dispatcher.dispatch(
            crawler_name="calendar",
            user_info=user_info,
            directory_path=directory_path
        )
        logger.info("✅ Calendar 크롤링 완료")
        return True
    except Exception as e:
        logger.error(f"❌ Calendar 크롤링 실패: {e}")
        return False


def crawl_google_calendar(
    user_first_name: str,
    user_last_name: str,
    calendar_id: Optional[str] = None,
    max_results: int = 2500
) -> bool:
    """
    Google Calendar API를 통해 데이터를 크롤링합니다.

    Args:
        user_first_name: 사용자 이름
        user_last_name: 사용자 성
        calendar_id: 특정 캘린더 ID (None이면 모든 캘린더)
        max_results: 최대 결과 수

    Returns:
        성공 여부
    """
    logger.info("📆 Google Calendar 크롤링 시작...")

    try:
        user_info = {"first_name": user_first_name, "last_name": user_last_name}
        dispatcher = CrawlerDispatcher()

        kwargs = {"max_results": max_results}
        if calendar_id:
            kwargs["calendar_id"] = calendar_id

        dispatcher.dispatch(
            crawler_name="google_calendar",
            user_info=user_info,
            **kwargs
        )
        logger.info("✅ Google Calendar 크롤링 완료")
        return True
    except Exception as e:
        logger.error(f"❌ Google Calendar 크롤링 실패: {e}")
        return False


def crawl_notion(
    user_first_name: str,
    user_last_name: str
) -> bool:
    """
    Notion 페이지를 크롤링합니다.

    Args:
        user_first_name: 사용자 이름
        user_last_name: 사용자 성

    Returns:
        성공 여부
    """
    logger.info("📝 Notion 크롤링 시작...")

    try:
        user_info = {"first_name": user_first_name, "last_name": user_last_name}
        dispatcher = CrawlerDispatcher()
        dispatcher.dispatch(
            crawler_name="notion",
            user_info=user_info
        )
        logger.info("✅ Notion 크롤링 완료")
        return True
    except Exception as e:
        logger.error(f"❌ Notion 크롤링 실패: {e}")
        return False


# NOTE: 네이버 크롤러는 현재 문제가 있어 비활성화
# def crawl_naver(
#     user_first_name: str,
#     user_last_name: str,
#     blog_id: str,
#     max_pages: Optional[int] = None
# ) -> bool:
#     """네이버 블로그 크롤링 (현재 비활성화)"""
#     pass


def crawl_all(
    user_first_name: str,
    user_last_name: str,
    skip_calendar: bool = False,
    skip_google_calendar: bool = False,
    skip_notion: bool = False,
    calendar_directory: str = "llm_engineering/application/crawlers/data",
    google_calendar_id: Optional[str] = None,
    google_max_results: int = 2500
) -> dict:
    """
    모든 활성화된 소스에서 데이터를 크롤링합니다.

    Args:
        user_first_name: 사용자 이름
        user_last_name: 사용자 성
        skip_calendar: Calendar 크롤링 건너뛰기
        skip_google_calendar: Google Calendar 크롤링 건너뛰기
        skip_notion: Notion 크롤링 건너뛰기
        calendar_directory: Calendar 엑셀 파일 경로
        google_calendar_id: 특정 Google Calendar ID
        google_max_results: Google Calendar 최대 결과 수

    Returns:
        각 소스별 성공 여부 딕셔너리
    """
    logger.info("=" * 70)
    logger.info("🚀 전체 크롤링 시작")
    logger.info("=" * 70)

    results = {}

    # Calendar 크롤링
    if not skip_calendar:
        results["calendar"] = crawl_calendar(
            user_first_name, user_last_name, calendar_directory
        )
    else:
        logger.info("⏭️ Calendar 크롤링 건너뜀")
        results["calendar"] = None

    # Google Calendar 크롤링
    if not skip_google_calendar:
        results["google_calendar"] = crawl_google_calendar(
            user_first_name, user_last_name, google_calendar_id, google_max_results
        )
    else:
        logger.info("⏭️ Google Calendar 크롤링 건너뜀")
        results["google_calendar"] = None

    # Notion 크롤링
    if not skip_notion:
        results["notion"] = crawl_notion(user_first_name, user_last_name)
    else:
        logger.info("⏭️ Notion 크롤링 건너뜀")
        results["notion"] = None

    # NOTE: Naver 크롤러는 현재 비활성화
    # results["naver"] = None

    # 결과 요약
    logger.info("=" * 70)
    logger.info("📊 크롤링 결과 요약")
    for source, success in results.items():
        if success is None:
            status = "⏭️ 건너뜀"
        elif success:
            status = "✅ 성공"
        else:
            status = "❌ 실패"
        logger.info(f"  - {source}: {status}")
    logger.info("=" * 70)

    return results
