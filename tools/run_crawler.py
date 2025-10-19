# tools/run_crawler.py

import click
from loguru import logger

from llm_engineering.application.crawlers.dispatcher import CrawlerDispatcher

@click.command()
@click.option("--name", required=True, type=click.Choice(["calendar", "naver", "notion"]), help="The name of the crawler to run.")
# --- User options (now required) ---
@click.option("--user-first-name", required=True, help="User's first name.")
@click.option("--user-last-name", required=True, help="User's last name.")
# --- Crawler specific options ---
@click.option("--blog-id", help="Naver Blog ID (for naver crawler).")
@click.option("--max-pages", type=int, help="Max pages to crawl for Naver blog.")
@click.option("--directory-path", default="llm_engineering/application/crawlers/data", help="Directory path for calendar .xlsx files.")

def main(name: str, user_first_name: str, user_last_name: str, **kwargs):
    """
    A unified CLI to run various crawlers via the CrawlerDispatcher.
    """
    crawler_config = {k: v for k, v in kwargs.items() if v is not None}
    
    # CLI 인자로부터 동적으로 사용자 정보 생성
    user_info = {"first_name": user_first_name, "last_name": user_last_name}

    dispatcher = CrawlerDispatcher()
    dispatcher.dispatch(
        crawler_name=name,
        user_info=user_info,
        **crawler_config
    )

if __name__ == "__main__":
    main()