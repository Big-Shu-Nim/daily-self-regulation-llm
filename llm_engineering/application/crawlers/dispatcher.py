# llm_engineering/application/crawlers/dispatcher.py

from loguru import logger

from llm_engineering.domain.documents import UserDocument
from .base import BaseCrawler
from .calendar import CalendarCrawler
from .google_calendar import GoogleCalendarCrawler
from .naver import NaverCrawler
from .notion import NotionCrawler

# 실행할 크롤러의 '이름'과 '클래스'를 매핑하는 레지스트리
CRAWLER_REGISTRY = {
    "calendar": CalendarCrawler,
    "google_calendar": GoogleCalendarCrawler,
    "naver": NaverCrawler,
    "notion": NotionCrawler,
}

class CrawlerDispatcher:
    """
    A config-driven factory for creating and running crawlers.
    """
    def dispatch(self, crawler_name: str, user_info: dict, **crawler_config):
        """
        Dynamically creates and runs a crawler based on its name and config.

        Args:
            crawler_name: The name of the crawler to run (e.g., "naver").
            user_info: Dict with user details, e.g., {"first_name": "Eddie", "last_name": "Yun"}.
            **crawler_config: Keyword arguments specific to the crawler's __init__ and extract methods.
        """
        logger.info(f"--- 🚀 Dispatching crawler: '{crawler_name}' ---")

        # 1. 레지스트리에서 크롤러 클래스 찾기
        crawler_class = CRAWLER_REGISTRY.get(crawler_name)
        if not crawler_class:
            logger.error(f"Crawler '{crawler_name}' not found in registry.")
            raise ValueError(f"Unknown crawler name: {crawler_name}")

        try:
            # 2. 사용자 정보 가져오기
            logger.info(f"Getting user: {user_info}")
            user = UserDocument.get_or_create(**user_info)

            # 3. 크롤러 인스턴스 생성 (필요한 `__init__` 인자만 전달)
            # NaverCrawler는 `headless` 인자가 필요할 수 있음
            init_kwargs = {}
            if crawler_name == "naver" and "headless" in crawler_config:
                init_kwargs["headless"] = crawler_config.pop("headless")
            
            crawler_instance = crawler_class(**init_kwargs)
            logger.info(f"Successfully initialized {crawler_class.__name__}.")

            # 4. `extract` 메소드 실행 (user와 나머지 설정값 전달)
            logger.info(f"Executing extract with config: {crawler_config}")
            crawler_instance.extract(user=user, **crawler_config)

            logger.success(f"--- ✅ Crawler '{crawler_name}' finished successfully ---")

        except Exception as e:
            logger.exception(f"An error occurred while running crawler '{crawler_name}'.")
            logger.error(f"--- ❌ Crawler '{crawler_name}' failed ---")