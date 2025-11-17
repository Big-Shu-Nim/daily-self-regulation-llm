"""
Example script for running the preprocessing pipeline.

이 스크립트는 MongoDB에서 원본 데이터를 로드하고,
preprocessor를 통해 cleaned documents로 변환한 후,
다시 MongoDB에 저장하는 전체 파이프라인을 보여줍니다.

증분 처리 지원:
- 원본 문서의 last_edited_time과 cleaned 문서의 processed_at 비교
- 변경된 문서 또는 새 문서만 전처리
- 기존 cleaned 문서는 upsert로 업데이트
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Set

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from pydantic import UUID4
from llm_engineering.domain.documents import (
    CalendarDocument,
    GoogleCalendarDocument,
    NotionPageDocument,
    NaverPostDocument
)
from llm_engineering.domain.cleaned_documents import (
    CleanedCalendarDocument,
    CleanedNotionDocument,
    CleanedNaverDocument
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


def load_raw_data(incremental: bool = True):
    """
    MongoDB에서 원본 데이터를 로드합니다.

    Args:
        incremental: True이면 변경된 문서만, False이면 전체 문서
    """
    print("="*70)
    print(f"1. 원본 데이터 로딩 중... (증분 처리: {'ON' if incremental else 'OFF'})")
    print("="*70)

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
                time_column='end_datetime'  # Calendar는 end_datetime 사용
            )
            print(f"✅ Calendar: {len(df_calendar)}건 처리 필요 (전체 {total_calendar}건)")
        else:
            print(f"✅ Calendar: {len(df_calendar)}건 로드")
    except Exception as e:
        print(f"❌ Calendar 로드 실패: {e}")
        df_calendar = pd.DataFrame()

    # Google Calendar 데이터 로드
    try:
        google_calendar_docs = GoogleCalendarDocument.bulk_find(is_deleted=False)
        df_google_calendar = pd.DataFrame([doc.model_dump() for doc in google_calendar_docs])
        total_google_calendar = len(df_google_calendar)

        if incremental and not df_google_calendar.empty:
            # Google Calendar도 CleanedCalendarDocument 사용 (platform으로 구분)
            processed_map = get_processed_document_map(CleanedCalendarDocument)
            df_google_calendar = filter_documents_to_process(
                df_google_calendar,
                processed_map,
                time_column='last_synced_at'  # Google Calendar는 last_synced_at 사용
            )
            print(f"✅ Google Calendar: {len(df_google_calendar)}건 처리 필요 (전체 {total_google_calendar}건)")
        else:
            print(f"✅ Google Calendar: {len(df_google_calendar)}건 로드")
    except Exception as e:
        print(f"❌ Google Calendar 로드 실패: {e}")
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
            print(f"✅ Notion: {len(df_notion)}건 처리 필요 (전체 {total_notion}건)")
        else:
            print(f"✅ Notion: {len(df_notion)}건 로드")
    except Exception as e:
        print(f"❌ Notion 로드 실패: {e}")
        df_notion = pd.DataFrame()

    # Naver 데이터 로드
    try:
        naver_docs = NaverPostDocument.bulk_find()
        df_naver = pd.DataFrame([doc.model_dump() for doc in naver_docs])
        total_naver = len(df_naver)

        if incremental and not df_naver.empty:
            processed_map = get_processed_document_map(CleanedNaverDocument)
            # Naver는 published_at 사용 (변경되지 않으므로 새 문서만 처리)
            df_naver = filter_documents_to_process(
                df_naver,
                processed_map,
                time_column='published_at'
            )
            print(f"✅ Naver: {len(df_naver)}건 처리 필요 (전체 {total_naver}건)")
        else:
            print(f"✅ Naver: {len(df_naver)}건 로드")
    except Exception as e:
        print(f"❌ Naver 로드 실패: {e}")
        df_naver = pd.DataFrame()

    print()
    return df_calendar, df_google_calendar, df_notion, df_naver


def preprocess_data(df_calendar, df_google_calendar, df_notion, df_naver):
    """데이터를 전처리합니다."""
    print("="*70)
    print("2. 데이터 전처리 중...")
    print("="*70)

    dispatcher = PreprocessorDispatcher(verbose=True)

    # 설정
    configs = {
        "calendar": {
            "category_rename_rules": [
                {"old": "yoonhs010@gmail.com", "new": "구글캘린더", "before_date": "2025-10-24"},
                {"old": "유지 / 정리", "new": "이동", "before_date": "2025-09-27"}
            ]
        },
        "google_calendar": {},  # Google Calendar는 간소화된 전처리 (설정 불필요)
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

    print()
    return all_cleaned


def save_cleaned_documents(cleaned_data):
    """
    Cleaned documents를 MongoDB에 저장합니다.

    Bulk Upsert 방식:
    - original_id 기준으로 기존 문서 찾아서 _id 매칭
    - bulk_write API로 일괄 upsert
    - 기존 문서가 있으면 업데이트, 없으면 삽입
    """
    print("="*70)
    print("3. Cleaned Documents 저장 중 (Bulk Upsert)...")
    print("="*70)

    def prepare_docs_for_upsert(doc_class, docs):
        """
        Upsert를 위해 문서 준비: 기존 문서의 _id를 찾아서 할당

        Args:
            doc_class: CleanedDocument 클래스
            docs: 새 문서 리스트

        Returns:
            준비된 문서 리스트
        """
        # 기존 문서들을 original_id로 매핑
        existing_docs = doc_class.bulk_find()
        existing_map = {str(doc.original_id): doc.id for doc in existing_docs}

        # 새 문서에 기존 _id 할당
        for doc in docs:
            original_id_str = str(doc.original_id)
            if original_id_str in existing_map:
                # 기존 문서가 있으면 _id 유지
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
            print(f"✅ Calendar: {len(calendar_docs)}건 처리 "
                  f"(수정: {result['modified']}, 신규: {result['upserted']})")

    # Google Calendar (CleanedCalendarDocument 공유 사용, platform으로 구분)
    if cleaned_data.get("google_calendar"):
        google_calendar_docs = [
            CleanedCalendarDocument(**doc) for doc in cleaned_data["google_calendar"]
        ]
        if google_calendar_docs:
            google_calendar_docs = prepare_docs_for_upsert(CleanedCalendarDocument, google_calendar_docs)
            result = CleanedCalendarDocument.bulk_upsert(google_calendar_docs, match_field="_id")
            print(f"✅ Google Calendar: {len(google_calendar_docs)}건 처리 "
                  f"(수정: {result['modified']}, 신규: {result['upserted']})")

    # Notion
    if cleaned_data.get("notion"):
        notion_docs = [
            CleanedNotionDocument(**doc) for doc in cleaned_data["notion"]
        ]
        if notion_docs:
            notion_docs = prepare_docs_for_upsert(CleanedNotionDocument, notion_docs)
            result = CleanedNotionDocument.bulk_upsert(notion_docs, match_field="_id")
            print(f"✅ Notion: {len(notion_docs)}건 처리 "
                  f"(수정: {result['modified']}, 신규: {result['upserted']})")

    # Naver
    if cleaned_data.get("naver"):
        naver_docs = [
            CleanedNaverDocument(**doc) for doc in cleaned_data["naver"]
        ]
        if naver_docs:
            naver_docs = prepare_docs_for_upsert(CleanedNaverDocument, naver_docs)
            result = CleanedNaverDocument.bulk_upsert(naver_docs, match_field="_id")
            print(f"✅ Naver: {len(naver_docs)}건 처리 "
                  f"(수정: {result['modified']}, 신규: {result['upserted']})")

    print()


def print_sample_documents(cleaned_data):
    """샘플 문서를 출력합니다."""
    print("="*70)
    print("4. 샘플 Cleaned Documents")
    print("="*70)

    # Calendar 샘플
    if cleaned_data.get("calendar"):
        print("\n[Calendar 샘플]")
        sample = cleaned_data["calendar"][0]
        print(f"ref_date: {sample['ref_date']}")
        print(f"doc_type: {sample['doc_type']}")
        print(f"content 미리보기:")
        print(sample['content'][:200] + "..." if len(sample['content']) > 200 else sample['content'])
        print()

    # Notion 샘플
    if cleaned_data.get("notion"):
        print("\n[Notion 샘플]")
        sample = cleaned_data["notion"][0]
        print(f"ref_date: {sample['ref_date']}")
        print(f"doc_type: {sample['doc_type']}")
        print(f"content 미리보기:")
        print(sample['content'][:200] + "..." if len(sample['content']) > 200 else sample['content'])
        print()

    # Naver 샘플
    if cleaned_data.get("naver"):
        print("\n[Naver 샘플]")
        sample = cleaned_data["naver"][0]
        print(f"ref_date: {sample['ref_date']}")
        print(f"doc_type: {sample['doc_type']}")
        print(f"content 미리보기:")
        print(sample['content'][:200] + "..." if len(sample['content']) > 200 else sample['content'])
        print()


import argparse

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description="데이터 전처리 파이프라인 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 증분 처리 (기본값, 변경된 문서만 처리)
  python tools/run_preprocessing.py --save

  # 전체 재처리 (모든 문서 강제 처리)
  python tools/run_preprocessing.py --save --full

  # 증분 처리 결과만 확인 (저장 안함)
  python tools/run_preprocessing.py
        """
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='전처리된 데이터를 MongoDB에 저장합니다.'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='전체 재처리 (증분 처리 비활성화). 모든 문서를 강제로 처리합니다.'
    )
    args = parser.parse_args()

    incremental = not args.full

    print("\n" + "="*70)
    print(f"데이터 전처리 파이프라인 실행 ({'증분 처리' if incremental else '전체 재처리'})")
    print("="*70 + "\n")

    # 1. 원본 데이터 로드 (증분 처리 옵션)
    df_calendar, df_google_calendar, df_notion, df_naver = load_raw_data(incremental=incremental)

    # 2. 전처리
    cleaned_data = preprocess_data(df_calendar, df_google_calendar, df_notion, df_naver)

    # 3. 샘플 출력
    print_sample_documents(cleaned_data)

    # 4. MongoDB에 저장 (선택적)
    if args.save:
        save_cleaned_documents(cleaned_data)
        print("\n✅ 모든 작업이 완료되었습니다!")
    else:
        print("\n⚠️ --save 옵션이 없어 저장하지 않고 종료합니다.")
        print("   저장을 원하시면 --save 플래그를 추가하여 실행하세요.")


    # 5. 통계 출력
    print("\n" + "="*70)
    print("최종 통계")
    print("="*70)
    total_cleaned = sum(len(docs) for docs in cleaned_data.values())
    print(f"총 Cleaned Documents: {total_cleaned}건")
    for platform, docs in cleaned_data.items():
        print(f"  - {platform}: {len(docs)}건")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
