"""
Date-filtered embedding pipeline.

2025년 6월 이후 데이터만 임베딩합니다.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from llm_engineering.domain.cleaned_documents import (
    CleanedCalendarDocument,
    CleanedNotionDocument,
    CleanedNaverDocument,
)
from llm_engineering.domain.embedded_documents import (
    EmbeddedCalendarDocument,
    EmbeddedNotionDocument,
    EmbeddedNaverDocument,
)
from llm_engineering.application.preprocessing.embedding_handlers import (
    CalendarEmbeddingHandler,
    NotionEmbeddingHandler,
    NaverEmbeddingHandler,
)

START_DATE = "2025-06-01"


def load_and_filter_documents():
    """2025년 6월 이후 문서만 로드"""
    print("=" * 70)
    print("1. 2025년 6월 이후 문서 로딩 중...")
    print("=" * 70)

    result = {}

    # Calendar
    try:
        print("⏳ Calendar 문서 로딩 및 필터링 중...")
        calendar_docs = list(CleanedCalendarDocument.bulk_find())
        calendar_filtered = [doc for doc in calendar_docs if doc.ref_date >= START_DATE]
        result["calendar"] = calendar_filtered
        print(f"✅ Calendar: {len(calendar_filtered)}건 (전체: {len(calendar_docs)}건)")
    except Exception as e:
        print(f"❌ Calendar 로드 실패: {e}")
        result["calendar"] = []

    # Notion
    try:
        print("⏳ Notion 문서 로딩 및 필터링 중...")
        notion_docs = list(CleanedNotionDocument.bulk_find())
        notion_filtered = [doc for doc in notion_docs if doc.ref_date and doc.ref_date >= START_DATE]
        result["notion"] = notion_filtered
        print(f"✅ Notion: {len(notion_filtered)}건 (전체: {len(notion_docs)}건)")
    except Exception as e:
        print(f"❌ Notion 로드 실패: {e}")
        result["notion"] = []

    # Naver
    try:
        print("⏳ Naver 문서 로딩 및 필터링 중...")
        naver_docs = list(CleanedNaverDocument.bulk_find())
        naver_filtered = [doc for doc in naver_docs if doc.ref_date and doc.ref_date >= START_DATE]
        result["naver"] = naver_filtered
        print(f"✅ Naver: {len(naver_filtered)}건 (전체: {len(naver_docs)}건)")
    except Exception as e:
        print(f"❌ Naver 로드 실패: {e}")
        result["naver"] = []

    total = sum(len(docs) for docs in result.values())
    print(f"\n📊 총 {total}건 로드 완료")
    print("=" * 70 + "\n")

    return result


def embed_documents(cleaned_docs):
    """문서 임베딩"""
    print("=" * 70)
    print("2. Documents 임베딩 중...")
    print("=" * 70)

    result = {}

    # Calendar
    if cleaned_docs.get("calendar"):
        docs = cleaned_docs["calendar"]
        print(f"⏳ Calendar 임베딩 중... ({len(docs)}건)")
        try:
            handler = CalendarEmbeddingHandler()
            embedded = handler.embed_batch(docs)
            result["calendar"] = embedded
            print(f"✅ Calendar: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            print(f"❌ Calendar 임베딩 실패: {e}")
            import traceback
            traceback.print_exc()
            result["calendar"] = []

    # Notion
    if cleaned_docs.get("notion"):
        docs = cleaned_docs["notion"]
        print(f"⏳ Notion 임베딩 중... ({len(docs)}건)")
        try:
            handler = NotionEmbeddingHandler()
            embedded = handler.embed_batch(docs)
            result["notion"] = embedded
            print(f"✅ Notion: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            print(f"❌ Notion 임베딩 실패: {e}")
            import traceback
            traceback.print_exc()
            result["notion"] = []

    # Naver
    if cleaned_docs.get("naver"):
        docs = cleaned_docs["naver"]
        print(f"⏳ Naver 임베딩 중... ({len(docs)}건)")
        try:
            handler = NaverEmbeddingHandler()
            embedded = handler.embed_batch(docs)
            result["naver"] = embedded
            print(f"✅ Naver: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            print(f"❌ Naver 임베딩 실패: {e}")
            import traceback
            traceback.print_exc()
            result["naver"] = []

    print("=" * 70 + "\n")
    return result


def save_to_qdrant(embedded_docs):
    """Qdrant에 저장"""
    print("=" * 70)
    print("3. Qdrant에 저장 중...")
    print("=" * 70)

    result = {}

    # Calendar
    if embedded_docs.get("calendar"):
        docs = embedded_docs["calendar"]
        print(f"⏳ Calendar 저장 중... ({len(docs)}건)")
        try:
            success = EmbeddedCalendarDocument.bulk_insert(docs)
            if success:
                result["calendar"] = len(docs)
                print(f"✅ Calendar: {len(docs)}건 저장 완료")
            else:
                result["calendar"] = 0
                print("❌ Calendar 저장 실패")
        except Exception as e:
            print(f"❌ Calendar 저장 실패: {e}")
            import traceback
            traceback.print_exc()
            result["calendar"] = 0

    # Notion
    if embedded_docs.get("notion"):
        docs = embedded_docs["notion"]
        print(f"⏳ Notion 저장 중... ({len(docs)}건)")
        try:
            success = EmbeddedNotionDocument.bulk_insert(docs)
            if success:
                result["notion"] = len(docs)
                print(f"✅ Notion: {len(docs)}건 저장 완료")
            else:
                result["notion"] = 0
                print("❌ Notion 저장 실패")
        except Exception as e:
            print(f"❌ Notion 저장 실패: {e}")
            import traceback
            traceback.print_exc()
            result["notion"] = 0

    # Naver
    if embedded_docs.get("naver"):
        docs = embedded_docs["naver"]
        print(f"⏳ Naver 저장 중... ({len(docs)}건)")
        try:
            success = EmbeddedNaverDocument.bulk_insert(docs)
            if success:
                result["naver"] = len(docs)
                print(f"✅ Naver: {len(docs)}건 저장 완료")
            else:
                result["naver"] = 0
                print("❌ Naver 저장 실패")
        except Exception as e:
            print(f"❌ Naver 저장 실패: {e}")
            import traceback
            traceback.print_exc()
            result["naver"] = 0

    print("=" * 70 + "\n")
    return result


def main():
    print("\n" + "=" * 70)
    print("2025년 6월 이후 데이터 임베딩 파이프라인")
    print("=" * 70)
    print(f"기준 날짜: {START_DATE} 이후")
    print("=" * 70 + "\n")

    try:
        # 1. 로드 및 필터링
        cleaned_docs = load_and_filter_documents()

        if not any(cleaned_docs.values()):
            print("❌ 로드된 데이터가 없습니다.")
            return

        # 2. 임베딩
        embedded_docs = embed_documents(cleaned_docs)

        if not any(embedded_docs.values()):
            print("⚠️ 임베딩된 문서가 없습니다.")
            return

        # 3. Qdrant 저장
        saved_counts = save_to_qdrant(embedded_docs)

        # 4. 최종 통계
        print("=" * 70)
        print("✅ 최종 통계")
        print("=" * 70)
        total = sum(saved_counts.values())
        print(f"총 저장된 문서: {total}건")
        for source, count in saved_counts.items():
            print(f"  - {source.capitalize()}: {count}건")
        print("=" * 70 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
