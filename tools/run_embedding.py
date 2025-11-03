"""
Embedding pipeline runner.

MongoDB의 CleanedDocuments를 로드하여 임베딩한 후
Qdrant에 저장합니다.

Usage:
    python tools/run_embedding.py
    python tools/run_embedding.py --limit 100
    python tools/run_embedding.py --source calendar --limit 50
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
from typing import List

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


def load_cleaned_documents(source: str = "all", limit: int = None):
    """
    MongoDB에서 CleanedDocuments를 로드합니다.

    Args:
        source: 로드할 소스 ("calendar", "notion", "naver", "all")
        limit: 최대 로드 개수 (None이면 전체)

    Returns:
        dict: {source_name: documents_list}
    """
    print("=" * 70)
    print("1. Cleaned Documents 로딩 중...")
    print("=" * 70)

    result = {}

    if source in ["calendar", "all"]:
        try:
            calendar_docs = list(CleanedCalendarDocument.bulk_find())
            if limit:
                calendar_docs = calendar_docs[:limit]
            result["calendar"] = calendar_docs
            print(f"✅ Calendar: {len(calendar_docs)}건 로드")
        except Exception as e:
            print(f"❌ Calendar 로드 실패: {e}")
            result["calendar"] = []

    if source in ["notion", "all"]:
        try:
            notion_docs = list(CleanedNotionDocument.bulk_find())
            if limit:
                notion_docs = notion_docs[:limit]
            result["notion"] = notion_docs
            print(f"✅ Notion: {len(notion_docs)}건 로드")
        except Exception as e:
            print(f"❌ Notion 로드 실패: {e}")
            result["notion"] = []

    if source in ["naver", "all"]:
        try:
            naver_docs = list(CleanedNaverDocument.bulk_find())
            if limit:
                naver_docs = naver_docs[:limit]
            result["naver"] = naver_docs
            print(f"✅ Naver: {len(naver_docs)}건 로드")
        except Exception as e:
            print(f"❌ Naver 로드 실패: {e}")
            result["naver"] = []

    print()
    return result


def embed_documents(cleaned_docs: dict):
    """
    CleanedDocuments를 임베딩하여 EmbeddedDocuments로 변환합니다.

    Args:
        cleaned_docs: {source_name: documents_list}

    Returns:
        dict: {source_name: embedded_documents_list}
    """
    print("=" * 70)
    print("2. Documents 임베딩 중...")
    print("=" * 70)

    result = {}

    # Calendar 임베딩
    if "calendar" in cleaned_docs and cleaned_docs["calendar"]:
        print(f"⏳ Calendar 문서 임베딩 중... ({len(cleaned_docs['calendar'])}건)")
        handler = CalendarEmbeddingHandler()
        try:
            embedded = handler.embed_batch(cleaned_docs["calendar"])
            result["calendar"] = embedded
            print(f"✅ Calendar: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            print(f"❌ Calendar 임베딩 실패: {e}")
            result["calendar"] = []

    # Notion 임베딩
    if "notion" in cleaned_docs and cleaned_docs["notion"]:
        print(f"⏳ Notion 문서 임베딩 중... ({len(cleaned_docs['notion'])}건)")
        handler = NotionEmbeddingHandler()
        try:
            embedded = handler.embed_batch(cleaned_docs["notion"])
            result["notion"] = embedded
            print(f"✅ Notion: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            print(f"❌ Notion 임베딩 실패: {e}")
            result["notion"] = []

    # Naver 임베딩
    if "naver" in cleaned_docs and cleaned_docs["naver"]:
        print(f"⏳ Naver 문서 임베딩 중... ({len(cleaned_docs['naver'])}건)")
        handler = NaverEmbeddingHandler()
        try:
            embedded = handler.embed_batch(cleaned_docs["naver"])
            result["naver"] = embedded
            print(f"✅ Naver: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            print(f"❌ Naver 임베딩 실패: {e}")
            result["naver"] = []

    print()
    return result


def save_to_qdrant(embedded_docs: dict):
    """
    EmbeddedDocuments를 Qdrant에 저장합니다.

    Args:
        embedded_docs: {source_name: embedded_documents_list}

    Returns:
        dict: {source_name: saved_count}
    """
    print("=" * 70)
    print("3. Qdrant에 저장 중...")
    print("=" * 70)

    result = {}

    # Calendar 저장
    if "calendar" in embedded_docs and embedded_docs["calendar"]:
        print(f"⏳ Calendar 저장 중... ({len(embedded_docs['calendar'])}건)")
        try:
            success = EmbeddedCalendarDocument.bulk_insert(embedded_docs["calendar"])
            if success:
                result["calendar"] = len(embedded_docs["calendar"])
                print(f"✅ Calendar: {len(embedded_docs['calendar'])}건 저장 완료")
            else:
                result["calendar"] = 0
                print("❌ Calendar 저장 실패")
        except Exception as e:
            print(f"❌ Calendar 저장 실패: {e}")
            result["calendar"] = 0

    # Notion 저장
    if "notion" in embedded_docs and embedded_docs["notion"]:
        print(f"⏳ Notion 저장 중... ({len(embedded_docs['notion'])}건)")
        try:
            success = EmbeddedNotionDocument.bulk_insert(embedded_docs["notion"])
            if success:
                result["notion"] = len(embedded_docs["notion"])
                print(f"✅ Notion: {len(embedded_docs['notion'])}건 저장 완료")
            else:
                result["notion"] = 0
                print("❌ Notion 저장 실패")
        except Exception as e:
            print(f"❌ Notion 저장 실패: {e}")
            result["notion"] = 0

    # Naver 저장
    if "naver" in embedded_docs and embedded_docs["naver"]:
        print(f"⏳ Naver 저장 중... ({len(embedded_docs['naver'])}건)")
        try:
            success = EmbeddedNaverDocument.bulk_insert(embedded_docs["naver"])
            if success:
                result["naver"] = len(embedded_docs["naver"])
                print(f"✅ Naver: {len(embedded_docs['naver'])}건 저장 완료")
            else:
                result["naver"] = 0
                print("❌ Naver 저장 실패")
        except Exception as e:
            print(f"❌ Naver 저장 실패: {e}")
            result["naver"] = 0

    print()
    return result


def print_summary(saved_counts: dict):
    """최종 통계를 출력합니다."""
    print("=" * 70)
    print("최종 통계")
    print("=" * 70)

    total = sum(saved_counts.values())
    print(f"총 저장된 문서: {total}건")
    for source, count in saved_counts.items():
        print(f"  - {source.capitalize()}: {count}건")

    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="CleanedDocuments를 임베딩하여 Qdrant에 저장합니다."
    )
    parser.add_argument(
        "--source",
        choices=["calendar", "notion", "naver", "all"],
        default="all",
        help="임베딩할 소스 선택 (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="각 소스별 최대 처리 개수 (default: 전체)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Qdrant에 저장하지 않고 임베딩만 테스트",
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("Embedding Pipeline 실행")
    print("=" * 70)
    print(f"소스: {args.source}")
    print(f"제한: {args.limit if args.limit else '없음'}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 70 + "\n")

    try:
        # 1. CleanedDocuments 로드
        cleaned_docs = load_cleaned_documents(source=args.source, limit=args.limit)

        if not any(cleaned_docs.values()):
            print("❌ 로드된 데이터가 없습니다. 먼저 preprocessing을 실행하세요.")
            print("   실행: python tools/run_preprocessing.py")
            return

        # 2. 임베딩 생성
        embedded_docs = embed_documents(cleaned_docs)

        if not any(embedded_docs.values()):
            print("⚠️ 임베딩된 문서가 없습니다.")
            return

        # 3. Qdrant에 저장 (dry-run이 아닐 때만)
        if not args.dry_run:
            saved_counts = save_to_qdrant(embedded_docs)
            print_summary(saved_counts)
            print("✅ 모든 작업이 완료되었습니다!")
        else:
            print("=" * 70)
            print("🔍 Dry Run 모드 - Qdrant 저장 생략")
            print("=" * 70)
            for source, docs in embedded_docs.items():
                if docs:
                    sample = docs[0]
                    print(f"\n{source.capitalize()} 샘플:")
                    print(f"  - ID: {sample.id}")
                    print(f"  - Ref Date: {sample.ref_date}")
                    print(f"  - Content: {sample.content[:100]}...")
                    print(f"  - Embedding size: {len(sample.embedding) if sample.embedding else 0}")
            print("\n" + "=" * 70)

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
