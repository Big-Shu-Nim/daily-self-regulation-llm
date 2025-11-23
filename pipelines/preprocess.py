"""
전처리 모듈.

MongoDB의 원본 문서를 로드하여 전처리 후 CleanedDocuments로 저장합니다.
증분 처리를 지원합니다.
"""

from datetime import datetime
from typing import Dict, Tuple

import pandas as pd
from loguru import logger

from llm_engineering.domain.documents import (
    CalendarDocument,
    GoogleCalendarDocument,
    NotionPageDocument,
    NaverPostDocument,
)
from llm_engineering.domain.cleaned_documents import (
    CleanedCalendarDocument,
    CleanedNotionDocument,
    CleanedNaverDocument,
)
from llm_engineering.application.preprocessing import PreprocessorDispatcher


def get_processed_document_map(cleaned_doc_class) -> Dict[str, datetime]:
    """
    Cleaned documents에서 original_id -> processed_at 매핑을 생성합니다.

    Args:
        cleaned_doc_class: CleanedDocument 클래스 (예: CleanedNotionDocument)

    Returns:
        {original_id: processed_at} 딕셔너리
    """
    try:
        cleaned_docs = cleaned_doc_class.bulk_find()
        return {
            str(doc.original_id): doc.processed_at
            for doc in cleaned_docs
        }
    except Exception:
        return {}


def filter_documents_to_process(
    df: pd.DataFrame,
    processed_map: Dict[str, datetime],
    time_column: str = 'last_edited_time'
) -> pd.DataFrame:
    """
    전처리가 필요한 문서만 필터링합니다.

    조건:
    1. Cleaned 문서가 없는 경우 (새 문서)
    2. 원본 문서의 time_column > cleaned 문서의 processed_at (변경된 문서)

    Args:
        df: 원본 문서 DataFrame
        processed_map: {original_id: processed_at} 매핑
        time_column: 비교할 시간 컬럼 (기본: last_edited_time)

    Returns:
        필터링된 DataFrame
    """
    if df.empty:
        return df

    def needs_processing(row):
        doc_id = str(row['id'])

        # 1. Cleaned 문서가 없으면 처리 필요
        if doc_id not in processed_map:
            return True

        # 2. 시간 비교 (원본이 더 최신이면 처리 필요)
        original_time = row.get(time_column)
        if pd.notna(original_time):
            processed_time = processed_map[doc_id]
            # datetime 객체로 변환 (필요시)
            if not isinstance(original_time, datetime):
                original_time = pd.to_datetime(original_time)
            return original_time > processed_time

        return False

    mask = df.apply(needs_processing, axis=1)
    return df[mask].copy()


def load_raw_data(incremental: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    MongoDB에서 원본 데이터를 로드합니다.

    Args:
        incremental: True이면 변경된 문서만, False이면 전체 문서

    Returns:
        (df_calendar, df_google_calendar, df_notion, df_naver) 튜플
    """
    logger.info("=" * 70)
    logger.info(f"📥 원본 데이터 로딩 중... (증분 처리: {'ON' if incremental else 'OFF'})")
    logger.info("=" * 70)

    # Calendar 데이터 로드
    try:
        calendar_docs = CalendarDocument.bulk_find()
        df_calendar = pd.DataFrame([doc.model_dump() for doc in calendar_docs])
        total_calendar = len(df_calendar)

        if incremental and not df_calendar.empty:
            processed_map = get_processed_document_map(CleanedCalendarDocument)
            df_calendar = filter_documents_to_process(
                df_calendar,
                processed_map,
                time_column='end_datetime'
            )
            logger.info(f"✅ Calendar: {len(df_calendar)}건 처리 필요 (전체 {total_calendar}건)")
        else:
            logger.info(f"✅ Calendar: {len(df_calendar)}건 로드")
    except Exception as e:
        logger.error(f"❌ Calendar 로드 실패: {e}")
        df_calendar = pd.DataFrame()

    # Google Calendar 데이터 로드
    try:
        google_calendar_docs = GoogleCalendarDocument.bulk_find(is_deleted=False)
        df_google_calendar = pd.DataFrame([doc.model_dump() for doc in google_calendar_docs])
        total_google_calendar = len(df_google_calendar)

        if incremental and not df_google_calendar.empty:
            processed_map = get_processed_document_map(CleanedCalendarDocument)
            df_google_calendar = filter_documents_to_process(
                df_google_calendar,
                processed_map,
                time_column='last_synced_at'
            )
            logger.info(f"✅ Google Calendar: {len(df_google_calendar)}건 처리 필요 (전체 {total_google_calendar}건)")
        else:
            logger.info(f"✅ Google Calendar: {len(df_google_calendar)}건 로드")
    except Exception as e:
        logger.error(f"❌ Google Calendar 로드 실패: {e}")
        df_google_calendar = pd.DataFrame()

    # Notion 데이터 로드
    try:
        notion_docs = NotionPageDocument.bulk_find()
        df_notion = pd.DataFrame([doc.model_dump() for doc in notion_docs])
        total_notion = len(df_notion)

        if incremental and not df_notion.empty:
            processed_map = get_processed_document_map(CleanedNotionDocument)
            df_notion = filter_documents_to_process(
                df_notion,
                processed_map,
                time_column='last_edited_time'
            )
            logger.info(f"✅ Notion: {len(df_notion)}건 처리 필요 (전체 {total_notion}건)")
        else:
            logger.info(f"✅ Notion: {len(df_notion)}건 로드")
    except Exception as e:
        logger.error(f"❌ Notion 로드 실패: {e}")
        df_notion = pd.DataFrame()

    # Naver 데이터 로드
    try:
        naver_docs = NaverPostDocument.bulk_find()
        df_naver = pd.DataFrame([doc.model_dump() for doc in naver_docs])
        total_naver = len(df_naver)

        if incremental and not df_naver.empty:
            processed_map = get_processed_document_map(CleanedNaverDocument)
            df_naver = filter_documents_to_process(
                df_naver,
                processed_map,
                time_column='published_at'
            )
            logger.info(f"✅ Naver: {len(df_naver)}건 처리 필요 (전체 {total_naver}건)")
        else:
            logger.info(f"✅ Naver: {len(df_naver)}건 로드")
    except Exception as e:
        logger.error(f"❌ Naver 로드 실패: {e}")
        df_naver = pd.DataFrame()

    return df_calendar, df_google_calendar, df_notion, df_naver


def preprocess_data(
    df_calendar: pd.DataFrame,
    df_google_calendar: pd.DataFrame,
    df_notion: pd.DataFrame,
    df_naver: pd.DataFrame,
    verbose: bool = True
) -> dict:
    """
    데이터를 전처리합니다.

    Args:
        df_calendar: Calendar DataFrame
        df_google_calendar: Google Calendar DataFrame
        df_notion: Notion DataFrame
        df_naver: Naver DataFrame
        verbose: 상세 로그 출력 여부

    Returns:
        전처리된 데이터 딕셔너리 {source: cleaned_docs_list}
    """
    logger.info("=" * 70)
    logger.info("🔄 데이터 전처리 중...")
    logger.info("=" * 70)

    dispatcher = PreprocessorDispatcher(verbose=verbose)

    # 설정
    configs = {
        "calendar": {
            "category_rename_rules": [
                {"old": "yoonhs010@gmail.com", "new": "구글캘린더", "before_date": "2025-10-24"},
                {"old": "유지 / 정리", "new": "이동", "before_date": "2025-09-27"}
            ]
        },
        "google_calendar": {},
        "naver": {
            "filter_categories": ["일일피드백"]
        }
    }

    # 전처리 실행
    all_cleaned = dispatcher.preprocess_all(
        {
            "calendar": df_calendar,
            "google_calendar": df_google_calendar,
            "notion": df_notion,
            "naver": df_naver
        },
        configs=configs
    )

    return all_cleaned


def save_cleaned_documents(cleaned_data: dict) -> dict:
    """
    Cleaned documents를 MongoDB에 저장합니다.

    Args:
        cleaned_data: 전처리된 데이터 딕셔너리

    Returns:
        저장 결과 딕셔너리 {source: {modified: int, upserted: int}}
    """
    logger.info("=" * 70)
    logger.info("💾 Cleaned Documents 저장 중 (Bulk Upsert)...")
    logger.info("=" * 70)

    results = {}

    def prepare_docs_for_upsert(doc_class, docs):
        """Upsert를 위해 문서 준비: 기존 문서의 _id를 찾아서 할당"""
        existing_docs = doc_class.bulk_find()
        existing_map = {str(doc.original_id): doc.id for doc in existing_docs}

        for doc in docs:
            original_id_str = str(doc.original_id)
            if original_id_str in existing_map:
                doc.id = existing_map[original_id_str]

        return docs

    # Calendar
    if cleaned_data.get("calendar"):
        calendar_docs = [
            CleanedCalendarDocument(**doc) for doc in cleaned_data["calendar"]
        ]
        if calendar_docs:
            calendar_docs = prepare_docs_for_upsert(CleanedCalendarDocument, calendar_docs)
            result = CleanedCalendarDocument.bulk_upsert(calendar_docs, match_field="_id")
            results["calendar"] = result
            logger.info(f"✅ Calendar: {len(calendar_docs)}건 처리 "
                       f"(수정: {result['modified']}, 신규: {result['upserted']})")

    # Google Calendar
    if cleaned_data.get("google_calendar"):
        google_calendar_docs = [
            CleanedCalendarDocument(**doc) for doc in cleaned_data["google_calendar"]
        ]
        if google_calendar_docs:
            google_calendar_docs = prepare_docs_for_upsert(CleanedCalendarDocument, google_calendar_docs)
            result = CleanedCalendarDocument.bulk_upsert(google_calendar_docs, match_field="_id")
            results["google_calendar"] = result
            logger.info(f"✅ Google Calendar: {len(google_calendar_docs)}건 처리 "
                       f"(수정: {result['modified']}, 신규: {result['upserted']})")

    # Notion
    if cleaned_data.get("notion"):
        notion_docs = [
            CleanedNotionDocument(**doc) for doc in cleaned_data["notion"]
        ]
        if notion_docs:
            notion_docs = prepare_docs_for_upsert(CleanedNotionDocument, notion_docs)
            result = CleanedNotionDocument.bulk_upsert(notion_docs, match_field="_id")
            results["notion"] = result
            logger.info(f"✅ Notion: {len(notion_docs)}건 처리 "
                       f"(수정: {result['modified']}, 신규: {result['upserted']})")

    # Naver
    if cleaned_data.get("naver"):
        naver_docs = [
            CleanedNaverDocument(**doc) for doc in cleaned_data["naver"]
        ]
        if naver_docs:
            naver_docs = prepare_docs_for_upsert(CleanedNaverDocument, naver_docs)
            result = CleanedNaverDocument.bulk_upsert(naver_docs, match_field="_id")
            results["naver"] = result
            logger.info(f"✅ Naver: {len(naver_docs)}건 처리 "
                       f"(수정: {result['modified']}, 신규: {result['upserted']})")

    return results


def run_preprocessing(
    incremental: bool = True,
    save: bool = True,
    verbose: bool = True
) -> dict:
    """
    전처리 파이프라인을 실행합니다.

    Args:
        incremental: 증분 처리 여부 (기본: True)
        save: MongoDB에 저장 여부 (기본: True)
        verbose: 상세 로그 출력 여부 (기본: True)

    Returns:
        전처리된 데이터 딕셔너리
    """
    logger.info("=" * 70)
    logger.info(f"🚀 전처리 파이프라인 실행 ({'증분 처리' if incremental else '전체 재처리'})")
    logger.info("=" * 70)

    # 1. 원본 데이터 로드
    df_calendar, df_google_calendar, df_notion, df_naver = load_raw_data(incremental=incremental)

    # 2. 전처리
    cleaned_data = preprocess_data(
        df_calendar, df_google_calendar, df_notion, df_naver, verbose=verbose
    )

    # 3. 저장
    if save:
        save_cleaned_documents(cleaned_data)
        logger.info("✅ 전처리 완료 및 저장됨")
    else:
        logger.info("⚠️ 전처리 완료 (저장 안함)")

    # 4. 통계
    total_cleaned = sum(len(docs) for docs in cleaned_data.values())
    logger.info(f"📊 총 처리된 문서: {total_cleaned}건")
    for platform, docs in cleaned_data.items():
        if docs:
            logger.info(f"   - {platform}: {len(docs)}건")

    return cleaned_data
