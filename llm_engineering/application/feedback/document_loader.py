"""
Document Loader for In-Context Feedback Generation.

MongoDB에서 cleaned documents를 날짜 기반으로 직접 조회합니다.
"""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from llm_engineering.domain.cleaned_documents import (
    CleanedCalendarDocument,
    CleanedNotionDocument,
    CleanedNaverDocument,
)


class DocumentLoader:
    """
    날짜 기반으로 cleaned documents를 로드하는 클래스.

    RAG와 달리, MongoDB에서 직접 쿼리하여 모든 문서를 가져옵니다.

    주간/월간 리포트 특별 처리:
    - Notion 주간 리포트는 metadata.week_start_date, week_end_date 기준으로 검색
    - 일반 문서는 ref_date 기준으로 검색
    """

    @staticmethod
    def load_by_date_range(
        start_date: str,
        end_date: str,
        sources: Optional[list[str]] = None,
        author_full_name: Optional[str] = None,
        include_weekly_reports: bool = True,
    ) -> list[dict]:
        """
        날짜 범위로 cleaned documents를 로드합니다.

        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD, inclusive)
            sources: 로드할 소스 리스트 (기본: ["calendar", "notion", "naver_blog"])
            author_full_name: 작성자 이름 (선택사항)
            include_weekly_reports: Notion 주간 리포트 포함 여부

        Returns:
            문서 리스트 (dict 형태, ref_date 기준 정렬)
        """
        if sources is None:
            sources = ["calendar", "notion", "naver_blog"]

        logger.info(
            f"Loading documents from {start_date} to {end_date}, sources={sources}"
        )

        all_docs = []

        # Calendar documents
        if "calendar" in sources:
            calendar_docs = DocumentLoader._load_calendar(
                start_date, end_date, author_full_name
            )
            all_docs.extend(calendar_docs)
            logger.debug(f"Loaded {len(calendar_docs)} calendar documents")

        # Notion documents
        if "notion" in sources:
            notion_docs = DocumentLoader._load_notion(
                start_date, end_date, author_full_name, include_weekly_reports
            )
            all_docs.extend(notion_docs)
            logger.debug(f"Loaded {len(notion_docs)} notion documents")

        # Naver documents
        if "naver_blog" in sources:
            naver_docs = DocumentLoader._load_naver(
                start_date, end_date, author_full_name
            )
            all_docs.extend(naver_docs)
            logger.debug(f"Loaded {len(naver_docs)} naver documents")

        # ref_date 기준 정렬
        all_docs.sort(key=lambda x: x.get("ref_date", ""))

        logger.info(f"Total {len(all_docs)} documents loaded")

        return all_docs

    @staticmethod
    def load_by_date(
        target_date: str,
        sources: Optional[list[str]] = None,
        author_full_name: Optional[str] = None,
    ) -> list[dict]:
        """
        특정 날짜의 documents를 로드합니다.

        Args:
            target_date: 대상 날짜 (YYYY-MM-DD)
            sources: 로드할 소스 리스트
            author_full_name: 작성자 이름 (선택사항)

        Returns:
            문서 리스트
        """
        return DocumentLoader.load_by_date_range(
            start_date=target_date,
            end_date=target_date,
            sources=sources,
            author_full_name=author_full_name,
            include_weekly_reports=False,  # 단일 날짜 조회 시 주간 리포트 제외
        )

    @staticmethod
    def load_with_context(
        target_date: str,
        include_previous: bool = True,
        include_next: bool = True,
        author_full_name: Optional[str] = None,
    ) -> dict[str, list[dict]]:
        """
        3일 윈도우(전날, 당일, 다음날)로 documents를 로드합니다.

        컨텍스트 로드 전략:
        - 전날: Calendar만 (저녁 활동 파악용)
        - 당일: 모든 소스 (Calendar, Notion, Naver)
        - 다음날: Calendar만 (아침 활동 파악용)

        Args:
            target_date: 대상 날짜 (YYYY-MM-DD)
            include_previous: 전날 포함 여부
            include_next: 다음날 포함 여부
            author_full_name: 작성자 이름 (선택사항)

        Returns:
            {
                "previous": [...],  # 전날 Calendar 문서 (include_previous=True일 때)
                "target": [...],    # 대상일 모든 소스 문서
                "next": [...]       # 다음날 Calendar 문서 (include_next=True일 때)
            }
        """
        logger.info(
            f"Loading documents with context for {target_date}, "
            f"prev={include_previous}, next={include_next}"
        )

        target_dt = datetime.strptime(target_date, "%Y-%m-%d")

        result = {"target": []}

        # 대상일 문서: 모든 소스
        result["target"] = DocumentLoader.load_by_date(
            target_date,
            sources=["calendar", "notion", "naver_blog"],
            author_full_name=author_full_name
        )

        # 전날 문서: Calendar만 (저녁 활동)
        if include_previous:
            prev_date = (target_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            result["previous"] = DocumentLoader.load_by_date(
                prev_date,
                sources=["calendar"],  # Calendar만
                author_full_name=author_full_name
            )

        # 다음날 문서: Calendar만 (아침 활동)
        if include_next:
            next_date = (target_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            result["next"] = DocumentLoader.load_by_date(
                next_date,
                sources=["calendar"],  # Calendar만
                author_full_name=author_full_name
            )

        return result

    @staticmethod
    def load_weekly_reports(
        start_date: str,
        end_date: str,
        author_full_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        주간 리포트를 로드합니다 (Notion 전용).

        week_start_date ~ week_end_date 기준으로 검색합니다.
        날짜 범위와 겹치는(overlap) 모든 주간 리포트를 반환합니다.

        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
            author_full_name: 작성자 이름 (선택사항)
            limit: 최대 개수 제한 (선택사항, 최신순)

        Returns:
            주간 리포트 문서 리스트 (week_start_date 기준 내림차순 정렬)
        """
        logger.info(f"Loading weekly reports from {start_date} to {end_date}")

        filters = {
            "doc_type": "weekly_report",
            "is_valid": True,
            # 날짜 범위 겹침 조건: week_start_date <= end_date AND week_end_date >= start_date
            "$and": [
                {"metadata.week_start_date": {"$lte": end_date}},
                {"metadata.week_end_date": {"$gte": start_date}},
            ],
        }

        if author_full_name:
            filters["author_full_name"] = author_full_name

        docs = CleanedNotionDocument.bulk_find(**filters)

        # week_start_date 기준 내림차순 정렬 (최신 -> 과거)
        docs = sorted(
            docs,
            key=lambda x: x.metadata.get("week_start_date", ""),
            reverse=True
        )

        if limit:
            docs = docs[:limit]

        logger.info(f"Loaded {len(docs)} weekly reports")

        return [doc.model_dump() for doc in docs]

    @staticmethod
    def _load_calendar(
        start_date: str, end_date: str, author_full_name: Optional[str]
    ) -> list[dict]:
        """Calendar documents 로드."""
        filters = {
            "ref_date": {"$gte": start_date, "$lte": end_date},
            "is_valid": True
        }

        if author_full_name:
            filters["author_full_name"] = author_full_name

        docs = CleanedCalendarDocument.bulk_find(**filters)
        return [doc.model_dump() for doc in docs]

    @staticmethod
    def _load_notion(
        start_date: str,
        end_date: str,
        author_full_name: Optional[str],
        include_weekly_reports: bool = True,
    ) -> list[dict]:
        """
        Notion documents 로드.

        주간 리포트 처리:
        - include_weekly_reports=False: ref_date 기준으로만 검색
        - include_weekly_reports=True: ref_date OR (week_start_date ~ week_end_date 겹침)
        """
        if not include_weekly_reports:
            # 주간 리포트 제외, ref_date만 사용
            filters = {
                "ref_date": {"$gte": start_date, "$lte": end_date},
                "is_valid": True,
            }
            if author_full_name:
                filters["author_full_name"] = author_full_name

            docs = CleanedNotionDocument.bulk_find(**filters)
            return [doc.model_dump() for doc in docs]

        # 주간 리포트 포함: 두 가지 쿼리 수행 후 병합

        # 1. ref_date 기준 일반 문서
        filters_normal = {
            "ref_date": {"$gte": start_date, "$lte": end_date},
            "is_valid": True,
        }
        if author_full_name:
            filters_normal["author_full_name"] = author_full_name

        normal_docs = CleanedNotionDocument.bulk_find(**filters_normal)

        # 2. 주간 리포트 (날짜 범위 겹침)
        filters_weekly = {
            "doc_type": "weekly_report",
            "is_valid": True,
            "$and": [
                {"metadata.week_start_date": {"$lte": end_date}},
                {"metadata.week_end_date": {"$gte": start_date}},
            ],
        }
        if author_full_name:
            filters_weekly["author_full_name"] = author_full_name

        weekly_docs = CleanedNotionDocument.bulk_find(**filters_weekly)

        # 중복 제거 (같은 ID가 있을 수 있음)
        seen_ids = set()
        all_docs = []

        for doc in list(normal_docs) + list(weekly_docs):
            doc_id = str(doc.id)
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_docs.append(doc.model_dump())

        return all_docs

    @staticmethod
    def _load_naver(
        start_date: str, end_date: str, author_full_name: Optional[str]
    ) -> list[dict]:
        """Naver documents 로드."""
        filters = {
            "ref_date": {"$gte": start_date, "$lte": end_date},
            "is_valid": True
        }

        if author_full_name:
            filters["author_full_name"] = author_full_name

        docs = CleanedNaverDocument.bulk_find(**filters)
        return [doc.model_dump() for doc in docs]
