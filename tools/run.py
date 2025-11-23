"""
파이프라인 실행 CLI.

크롤링, 전처리, 임베딩 파이프라인을 실행합니다.

사용법:
    # ETL 파이프라인 (크롤링 + 전처리)
    python tools/run.py --run-etl --first-name 홍 --last-name 길동

    # End-to-End 파이프라인 (크롤링 + 전처리 + 임베딩)
    python tools/run.py --run-end-to-end --first-name 홍 --last-name 길동

    # 전처리만
    python tools/run.py --run-preprocessing

    # 임베딩만
    python tools/run.py --run-embedding

    # 특정 소스만 크롤링
    python tools/run.py --run-etl --first-name 홍 --last-name 길동 --skip-calendar --skip-notion
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from loguru import logger

from pipelines import data_etl_pipeline, end_to_end_data_pipeline
from pipelines.preprocess import run_preprocessing
from pipelines.embed import run_embedding


@click.command(
    help="""
데이터 파이프라인 CLI.

크롤링, 전처리, 임베딩 파이프라인을 실행합니다.

Examples:

  # ETL 파이프라인 (크롤링 + 전처리)
  python tools/run.py --run-etl --first-name 홍 --last-name 길동

  # End-to-End 파이프라인 (크롤링 + 전처리 + 임베딩)
  python tools/run.py --run-end-to-end --first-name 홍 --last-name 길동

  # 전처리만
  python tools/run.py --run-preprocessing

  # 임베딩만
  python tools/run.py --run-embedding --source calendar
"""
)
# 파이프라인 선택
@click.option(
    "--run-end-to-end",
    is_flag=True,
    default=False,
    help="End-to-End 파이프라인 실행 (크롤링 + 전처리 + 임베딩)",
)
@click.option(
    "--run-etl",
    is_flag=True,
    default=False,
    help="ETL 파이프라인 실행 (크롤링 + 전처리)",
)
@click.option(
    "--run-preprocessing",
    is_flag=True,
    default=False,
    help="전처리만 실행",
)
@click.option(
    "--run-embedding",
    is_flag=True,
    default=False,
    help="임베딩만 실행",
)
# 사용자 정보
@click.option(
    "--first-name",
    default=None,
    help="사용자 이름 (크롤링 시 필수)",
)
@click.option(
    "--last-name",
    default=None,
    help="사용자 성 (크롤링 시 필수)",
)
# 크롤링 옵션
@click.option(
    "--skip-calendar",
    is_flag=True,
    default=False,
    help="Calendar 크롤링 건너뛰기",
)
@click.option(
    "--skip-google-calendar",
    is_flag=True,
    default=False,
    help="Google Calendar 크롤링 건너뛰기",
)
@click.option(
    "--skip-notion",
    is_flag=True,
    default=False,
    help="Notion 크롤링 건너뛰기",
)
@click.option(
    "--calendar-directory",
    default="llm_engineering/application/crawlers/data",
    help="Calendar 엑셀 파일 경로",
)
@click.option(
    "--google-calendar-id",
    default=None,
    help="특정 Google Calendar ID",
)
@click.option(
    "--google-max-results",
    default=2500,
    type=int,
    help="Google Calendar 최대 결과 수",
)
# 전처리 옵션
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="전체 재처리 (증분 처리 비활성화)",
)
@click.option(
    "--no-save",
    is_flag=True,
    default=False,
    help="전처리 결과를 저장하지 않음 (테스트용)",
)
# 임베딩 옵션
@click.option(
    "--source",
    type=click.Choice(["calendar", "notion", "naver", "all"]),
    default="all",
    help="임베딩할 소스 선택",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="각 소스별 최대 임베딩 개수",
)
@click.option(
    "--skip-embedding",
    is_flag=True,
    default=False,
    help="End-to-End에서 임베딩 단계 건너뛰기",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="임베딩 시 Qdrant 저장 없이 테스트만",
)
def main(
    run_end_to_end: bool,
    run_etl: bool,
    run_preprocessing: bool,
    run_embedding: bool,
    first_name: str,
    last_name: str,
    skip_calendar: bool,
    skip_google_calendar: bool,
    skip_notion: bool,
    calendar_directory: str,
    google_calendar_id: str,
    google_max_results: int,
    full: bool,
    no_save: bool,
    source: str,
    limit: int,
    skip_embedding: bool,
    dry_run: bool,
) -> None:
    """메인 CLI 함수."""

    # 액션 선택 확인
    if not any([run_end_to_end, run_etl, run_preprocessing, run_embedding]):
        logger.error("실행할 파이프라인을 선택하세요.")
        logger.info("  --run-end-to-end: 전체 파이프라인 (크롤링 + 전처리 + 임베딩)")
        logger.info("  --run-etl: ETL 파이프라인 (크롤링 + 전처리)")
        logger.info("  --run-preprocessing: 전처리만")
        logger.info("  --run-embedding: 임베딩만")
        return

    incremental = not full
    save_to_db = not no_save

    # End-to-End 파이프라인
    if run_end_to_end:
        if not first_name or not last_name:
            logger.error("--first-name과 --last-name이 필요합니다.")
            return

        end_to_end_data_pipeline(
            user_first_name=first_name,
            user_last_name=last_name,
            skip_calendar=skip_calendar,
            skip_google_calendar=skip_google_calendar,
            skip_notion=skip_notion,
            calendar_directory=calendar_directory,
            google_calendar_id=google_calendar_id,
            google_max_results=google_max_results,
            incremental=incremental,
            embedding_source=source,
            embedding_limit=limit,
            skip_embedding=skip_embedding,
        )

    # ETL 파이프라인
    if run_etl:
        if not first_name or not last_name:
            logger.error("--first-name과 --last-name이 필요합니다.")
            return

        data_etl_pipeline(
            user_first_name=first_name,
            user_last_name=last_name,
            skip_calendar=skip_calendar,
            skip_google_calendar=skip_google_calendar,
            skip_notion=skip_notion,
            calendar_directory=calendar_directory,
            google_calendar_id=google_calendar_id,
            google_max_results=google_max_results,
            incremental=incremental,
            save_to_db=save_to_db,
        )

    # 전처리만
    if run_preprocessing:
        from pipelines.preprocess import run_preprocessing as preprocess_fn
        preprocess_fn(
            incremental=incremental,
            save=save_to_db,
            verbose=True,
        )

    # 임베딩만
    if run_embedding:
        from pipelines.embed import run_embedding as embed_fn
        embed_fn(
            source=source,
            limit=limit,
            dry_run=dry_run,
        )


if __name__ == "__main__":
    main()
