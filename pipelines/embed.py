"""
임베딩 모듈.

CleanedDocuments를 임베딩하여 Qdrant에 저장합니다.
"""

from typing import Optional

from loguru import logger

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


def load_cleaned_documents(
    source: str = "all",
    limit: Optional[int] = None
) -> dict:
    """
    MongoDB에서 CleanedDocuments를 로드합니다.

    Args:
        source: 로드할 소스 ("calendar", "notion", "naver", "all")
        limit: 최대 로드 개수 (None이면 전체)

    Returns:
        dict: {source_name: documents_list}
    """
    logger.info("=" * 70)
    logger.info("📥 Cleaned Documents 로딩 중...")
    logger.info("=" * 70)

    result = {}

    if source in ["calendar", "all"]:
        try:
            calendar_docs = list(CleanedCalendarDocument.bulk_find())
            if limit:
                calendar_docs = calendar_docs[:limit]
            result["calendar"] = calendar_docs
            logger.info(f"✅ Calendar: {len(calendar_docs)}건 로드")
        except Exception as e:
            logger.error(f"❌ Calendar 로드 실패: {e}")
            result["calendar"] = []

    if source in ["notion", "all"]:
        try:
            notion_docs = list(CleanedNotionDocument.bulk_find())
            if limit:
                notion_docs = notion_docs[:limit]
            result["notion"] = notion_docs
            logger.info(f"✅ Notion: {len(notion_docs)}건 로드")
        except Exception as e:
            logger.error(f"❌ Notion 로드 실패: {e}")
            result["notion"] = []

    if source in ["naver", "all"]:
        try:
            naver_docs = list(CleanedNaverDocument.bulk_find())
            if limit:
                naver_docs = naver_docs[:limit]
            result["naver"] = naver_docs
            logger.info(f"✅ Naver: {len(naver_docs)}건 로드")
        except Exception as e:
            logger.error(f"❌ Naver 로드 실패: {e}")
            result["naver"] = []

    return result


def embed_documents(cleaned_docs: dict) -> dict:
    """
    CleanedDocuments를 임베딩하여 EmbeddedDocuments로 변환합니다.

    Args:
        cleaned_docs: {source_name: documents_list}

    Returns:
        dict: {source_name: embedded_documents_list}
    """
    logger.info("=" * 70)
    logger.info("🔄 Documents 임베딩 중...")
    logger.info("=" * 70)

    result = {}

    # Calendar 임베딩
    if "calendar" in cleaned_docs and cleaned_docs["calendar"]:
        logger.info(f"⏳ Calendar 문서 임베딩 중... ({len(cleaned_docs['calendar'])}건)")
        handler = CalendarEmbeddingHandler()
        try:
            embedded = handler.embed_batch(cleaned_docs["calendar"])
            result["calendar"] = embedded
            logger.info(f"✅ Calendar: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            logger.error(f"❌ Calendar 임베딩 실패: {e}")
            result["calendar"] = []

    # Notion 임베딩
    if "notion" in cleaned_docs and cleaned_docs["notion"]:
        logger.info(f"⏳ Notion 문서 임베딩 중... ({len(cleaned_docs['notion'])}건)")
        handler = NotionEmbeddingHandler()
        try:
            embedded = handler.embed_batch(cleaned_docs["notion"])
            result["notion"] = embedded
            logger.info(f"✅ Notion: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            logger.error(f"❌ Notion 임베딩 실패: {e}")
            result["notion"] = []

    # Naver 임베딩
    if "naver" in cleaned_docs and cleaned_docs["naver"]:
        logger.info(f"⏳ Naver 문서 임베딩 중... ({len(cleaned_docs['naver'])}건)")
        handler = NaverEmbeddingHandler()
        try:
            embedded = handler.embed_batch(cleaned_docs["naver"])
            result["naver"] = embedded
            logger.info(f"✅ Naver: {len(embedded)}건 임베딩 완료")
        except Exception as e:
            logger.error(f"❌ Naver 임베딩 실패: {e}")
            result["naver"] = []

    return result


def save_to_qdrant(embedded_docs: dict) -> dict:
    """
    EmbeddedDocuments를 Qdrant에 저장합니다.

    Args:
        embedded_docs: {source_name: embedded_documents_list}

    Returns:
        dict: {source_name: saved_count}
    """
    logger.info("=" * 70)
    logger.info("💾 Qdrant에 저장 중...")
    logger.info("=" * 70)

    result = {}

    # Calendar 저장
    if "calendar" in embedded_docs and embedded_docs["calendar"]:
        logger.info(f"⏳ Calendar 저장 중... ({len(embedded_docs['calendar'])}건)")
        try:
            success = EmbeddedCalendarDocument.bulk_insert(embedded_docs["calendar"])
            if success:
                result["calendar"] = len(embedded_docs["calendar"])
                logger.info(f"✅ Calendar: {len(embedded_docs['calendar'])}건 저장 완료")
            else:
                result["calendar"] = 0
                logger.error("❌ Calendar 저장 실패")
        except Exception as e:
            logger.error(f"❌ Calendar 저장 실패: {e}")
            result["calendar"] = 0

    # Notion 저장
    if "notion" in embedded_docs and embedded_docs["notion"]:
        logger.info(f"⏳ Notion 저장 중... ({len(embedded_docs['notion'])}건)")
        try:
            success = EmbeddedNotionDocument.bulk_insert(embedded_docs["notion"])
            if success:
                result["notion"] = len(embedded_docs["notion"])
                logger.info(f"✅ Notion: {len(embedded_docs['notion'])}건 저장 완료")
            else:
                result["notion"] = 0
                logger.error("❌ Notion 저장 실패")
        except Exception as e:
            logger.error(f"❌ Notion 저장 실패: {e}")
            result["notion"] = 0

    # Naver 저장
    if "naver" in embedded_docs and embedded_docs["naver"]:
        logger.info(f"⏳ Naver 저장 중... ({len(embedded_docs['naver'])}건)")
        try:
            success = EmbeddedNaverDocument.bulk_insert(embedded_docs["naver"])
            if success:
                result["naver"] = len(embedded_docs["naver"])
                logger.info(f"✅ Naver: {len(embedded_docs['naver'])}건 저장 완료")
            else:
                result["naver"] = 0
                logger.error("❌ Naver 저장 실패")
        except Exception as e:
            logger.error(f"❌ Naver 저장 실패: {e}")
            result["naver"] = 0

    return result


def run_embedding(
    source: str = "all",
    limit: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """
    임베딩 파이프라인을 실행합니다.

    Args:
        source: 임베딩할 소스 ("calendar", "notion", "naver", "all")
        limit: 각 소스별 최대 처리 개수
        dry_run: True이면 Qdrant 저장 없이 임베딩만 테스트

    Returns:
        저장 결과 딕셔너리
    """
    logger.info("=" * 70)
    logger.info("🚀 임베딩 파이프라인 실행")
    logger.info(f"   소스: {source}, 제한: {limit if limit else '없음'}, Dry run: {dry_run}")
    logger.info("=" * 70)

    # 1. CleanedDocuments 로드
    cleaned_docs = load_cleaned_documents(source=source, limit=limit)

    if not any(cleaned_docs.values()):
        logger.warning("❌ 로드된 데이터가 없습니다. 먼저 preprocessing을 실행하세요.")
        return {}

    # 2. 임베딩 생성
    embedded_docs = embed_documents(cleaned_docs)

    if not any(embedded_docs.values()):
        logger.warning("⚠️ 임베딩된 문서가 없습니다.")
        return {}

    # 3. Qdrant에 저장 (dry-run이 아닐 때만)
    if not dry_run:
        saved_counts = save_to_qdrant(embedded_docs)

        # 최종 통계
        total = sum(saved_counts.values())
        logger.info("=" * 70)
        logger.info(f"📊 총 저장된 문서: {total}건")
        for source_name, count in saved_counts.items():
            logger.info(f"   - {source_name.capitalize()}: {count}건")
        logger.info("=" * 70)

        return saved_counts
    else:
        logger.info("🔍 Dry Run 모드 - Qdrant 저장 생략")
        for source_name, docs in embedded_docs.items():
            if docs:
                sample = docs[0]
                logger.info(f"  {source_name.capitalize()} 샘플: {sample.content[:50]}...")
        return {"dry_run": True, "embedded_counts": {k: len(v) for k, v in embedded_docs.items()}}
