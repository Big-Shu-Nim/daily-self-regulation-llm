"""
Example script for running the preprocessing pipeline.

이 스크립트는 MongoDB에서 원본 데이터를 로드하고,
preprocessor를 통해 cleaned documents로 변환한 후,
다시 MongoDB에 저장하는 전체 파이프라인을 보여줍니다.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from llm_engineering.domain.documents import (
    CalendarDocument,
    NotionPageDocument,
    NaverPostDocument
)
from llm_engineering.domain.cleaned_documents import (
    CleanedCalendarDocument,
    CleanedNotionDocument,
    CleanedNaverDocument
)
from llm_engineering.application.preprocessing import PreprocessorDispatcher


def load_raw_data():
    """MongoDB에서 원본 데이터를 로드합니다."""
    print("="*70)
    print("1. 원본 데이터 로딩 중...")
    print("="*70)

    # Calendar 데이터 로드
    try:
        calendar_docs = CalendarDocument.bulk_find()
        df_calendar = pd.DataFrame([doc.model_dump() for doc in calendar_docs])
        print(f"✅ Calendar: {len(df_calendar)}건 로드")
    except Exception as e:
        print(f"❌ Calendar 로드 실패: {e}")
        df_calendar = pd.DataFrame()

    # Notion 데이터 로드
    try:
        notion_docs = NotionPageDocument.bulk_find()
        df_notion = pd.DataFrame([doc.model_dump() for doc in notion_docs])
        print(f"✅ Notion: {len(df_notion)}건 로드")
    except Exception as e:
        print(f"❌ Notion 로드 실패: {e}")
        df_notion = pd.DataFrame()

    # Naver 데이터 로드
    try:
        naver_docs = NaverPostDocument.bulk_find()
        df_naver = pd.DataFrame([doc.model_dump() for doc in naver_docs])
        print(f"✅ Naver: {len(df_naver)}건 로드")
    except Exception as e:
        print(f"❌ Naver 로드 실패: {e}")
        df_naver = pd.DataFrame()

    print()
    return df_calendar, df_notion, df_naver


def preprocess_data(df_calendar, df_notion, df_naver):
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
        "naver": {
            "filter_categories": ["일일피드백"]
        }
    }

    # 전처리 실행
    all_cleaned = dispatcher.preprocess_all(
        {
            "calendar": df_calendar,
            "notion": df_notion,
            "naver": df_naver
        },
        configs=configs
    )

    print()
    return all_cleaned


def save_cleaned_documents(cleaned_data):
    """Cleaned documents를 MongoDB에 대량 저장합니다."""
    print("="*70)
    print("3. Cleaned Documents 대량 저장 중...")
    print("="*70)

    # Calendar
    if cleaned_data.get("calendar"):
        calendar_docs = [
            CleanedCalendarDocument(**doc) for doc in cleaned_data["calendar"]
        ]
        if calendar_docs:
            CleanedCalendarDocument.bulk_insert(calendar_docs)
            print(f"✅ Calendar: {len(calendar_docs)}건 저장")

    # Notion
    if cleaned_data.get("notion"):
        notion_docs = [
            CleanedNotionDocument(**doc) for doc in cleaned_data["notion"]
        ]
        if notion_docs:
            CleanedNotionDocument.bulk_insert(notion_docs)
            print(f"✅ Notion: {len(notion_docs)}건 저장")

    # Naver
    if cleaned_data.get("naver"):
        naver_docs = [
            CleanedNaverDocument(**doc) for doc in cleaned_data["naver"]
        ]
        if naver_docs:
            CleanedNaverDocument.bulk_insert(naver_docs)
            print(f"✅ Naver: {len(naver_docs)}건 저장")

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
    parser = argparse.ArgumentParser(description="데이터 전처리 파이프라인 실행")
    parser.add_argument(
        '--save', 
        action='store_true', 
        help='전처리된 데이터를 MongoDB에 저장합니다.'
    )
    args = parser.parse_args()

    print("\n" + "="*70)
    print("데이터 전처리 파이프라인 실행")
    print("="*70 + "\n")

    # 1. 원본 데이터 로드
    df_calendar, df_notion, df_naver = load_raw_data()

    # 2. 전처리
    cleaned_data = preprocess_data(df_calendar, df_notion, df_naver)

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
