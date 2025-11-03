"""
RAG Document Retriever.

Qdrant에서 관련 문서를 검색하는 서비스입니다.
"""

from datetime import datetime, timedelta
from typing import Literal

from loguru import logger

from llm_engineering.application.networks.embeddings import EmbeddingModelSingleton
from llm_engineering.domain.embedded_documents import (
    EmbeddedCalendarDocument,
    EmbeddedNotionDocument,
    EmbeddedNaverDocument,
)
from llm_engineering.infrastructure.db.qdrant import connection


class DocumentRetriever:
    """
    RAG 검색을 위한 문서 검색 서비스.

    날짜 기반 또는 유사도 기반 검색을 지원합니다.
    """

    def __init__(self):
        """Initialize the retriever with embedding model."""
        self.embedding_model = EmbeddingModelSingleton()

    def retrieve_by_date_range(
        self,
        target_date: str,
        include_previous: bool = True,
        include_next: bool = True,
        source: Literal["calendar", "notion", "naver", "all"] = "all"
    ) -> dict[str, list]:
        """
        날짜 범위로 문서를 검색합니다.

        3일 컨텍스트: Day1(전날) → Day2(분석 대상) → Day3(다음날)

        Args:
            target_date: 분석 대상 날짜 (YYYY-MM-DD 형식)
            include_previous: 전날 데이터 포함 여부
            include_next: 다음날 데이터 포함 여부
            source: 검색할 소스 ("calendar", "notion", "naver", "all")

        Returns:
            dict: {
                "day1": [...],  # 전날 문서 (optional)
                "day2": [...],  # 분석 대상일 문서
                "day3": [...]   # 다음날 문서 (optional)
            }
        """
        logger.info(f"Retrieving documents for date range around {target_date}")

        # 날짜 파싱
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        prev_date = (target_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (target_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        result = {"day1": [], "day2": [], "day3": []}

        # Calendar 문서
        if source in ["calendar", "all"]:
            calendar_docs = self._retrieve_calendar_by_dates(
                target_date, prev_date if include_previous else None, next_date if include_next else None
            )
            result["day1"].extend(calendar_docs.get("day1", []))
            result["day2"].extend(calendar_docs.get("day2", []))
            result["day3"].extend(calendar_docs.get("day3", []))

        # Notion 문서
        if source in ["notion", "all"]:
            notion_docs = self._retrieve_notion_by_dates(
                target_date, prev_date if include_previous else None, next_date if include_next else None
            )
            result["day1"].extend(notion_docs.get("day1", []))
            result["day2"].extend(notion_docs.get("day2", []))
            result["day3"].extend(notion_docs.get("day3", []))

        # Naver 문서
        if source in ["naver", "all"]:
            naver_docs = self._retrieve_naver_by_dates(
                target_date, prev_date if include_previous else None, next_date if include_next else None
            )
            result["day1"].extend(naver_docs.get("day1", []))
            result["day2"].extend(naver_docs.get("day2", []))
            result["day3"].extend(naver_docs.get("day3", []))

        logger.info(
            f"Retrieved {len(result['day1'])} docs for day1, "
            f"{len(result['day2'])} docs for day2, "
            f"{len(result['day3'])} docs for day3"
        )

        return result

    def retrieve_by_similarity(
        self,
        query: str,
        limit: int = 10,
        source: Literal["calendar", "notion", "naver", "all"] = "all",
        min_score: float = 0.3
    ) -> list[dict]:
        """
        유사도 기반으로 문서를 검색합니다.

        Args:
            query: 검색 쿼리
            limit: 검색 결과 최대 개수
            source: 검색할 소스
            min_score: 최소 유사도 점수

        Returns:
            list: 검색된 문서 리스트 (점수 포함)
        """
        logger.info(f"Searching documents by similarity: '{query}' (limit={limit}, min_score={min_score})")

        # 쿼리 임베딩
        query_embedding = self.embedding_model(query, to_list=True)

        results = []

        # Calendar 검색
        if source in ["calendar", "all"]:
            calendar_results = connection.search(
                collection_name="embedded_calendar",
                query_vector=query_embedding,
                limit=limit
            )
            for result in calendar_results:
                if result.score >= min_score:
                    results.append({
                        "source": "calendar",
                        "score": result.score,
                        "content": result.payload.get("content", ""),
                        "ref_date": result.payload.get("ref_date", ""),
                        "metadata": result.payload.get("metadata", {})
                    })

        # Notion 검색
        if source in ["notion", "all"]:
            notion_results = connection.search(
                collection_name="embedded_notion",
                query_vector=query_embedding,
                limit=limit
            )
            for result in notion_results:
                if result.score >= min_score:
                    results.append({
                        "source": "notion",
                        "score": result.score,
                        "content": result.payload.get("content", ""),
                        "ref_date": result.payload.get("ref_date", ""),
                        "metadata": result.payload.get("metadata", {})
                    })

        # Naver 검색
        if source in ["naver", "all"]:
            naver_results = connection.search(
                collection_name="embedded_naver",
                query_vector=query_embedding,
                limit=limit
            )
            for result in naver_results:
                if result.score >= min_score:
                    results.append({
                        "source": "naver",
                        "score": result.score,
                        "content": result.payload.get("content", ""),
                        "ref_date": result.payload.get("ref_date", ""),
                        "metadata": result.payload.get("metadata", {})
                    })

        # 점수순으로 정렬
        results.sort(key=lambda x: x["score"], reverse=True)

        logger.info(f"Found {len(results)} documents with similarity >= {min_score}")

        return results[:limit]

    def _retrieve_calendar_by_dates(
        self, target_date: str, prev_date: str | None, next_date: str | None
    ) -> dict[str, list]:
        """Calendar 문서를 날짜로 검색합니다 (Python 필터링 사용)."""
        result = {"day1": [], "day2": [], "day3": []}

        try:
            # 모든 문서 가져오기 (scroll without filter)
            all_results = connection.scroll(
                collection_name="embedded_calendar",
                limit=10000  # 충분히 큰 값
            )

            # Python에서 날짜별로 필터링
            for point in all_results[0]:
                ref_date = point.payload.get("ref_date", "")

                doc = {
                    "source": "calendar",
                    "content": point.payload.get("content", ""),
                    "ref_date": ref_date,
                    "metadata": point.payload.get("metadata", {})
                }

                if ref_date == target_date:
                    result["day2"].append(doc)
                elif prev_date and ref_date == prev_date:
                    result["day1"].append(doc)
                elif next_date and ref_date == next_date:
                    result["day3"].append(doc)

        except Exception as e:
            logger.error(f"Error retrieving calendar documents: {e}")

        return result

    def _retrieve_notion_by_dates(
        self, target_date: str, prev_date: str | None, next_date: str | None
    ) -> dict[str, list]:
        """Notion 문서를 날짜로 검색합니다 (Python 필터링 사용)."""
        result = {"day1": [], "day2": [], "day3": []}

        try:
            # 모든 문서 가져오기
            all_results = connection.scroll(
                collection_name="embedded_notion",
                limit=1000
            )

            # Python에서 날짜별로 필터링
            for point in all_results[0]:
                ref_date = point.payload.get("ref_date", "")

                doc = {
                    "source": "notion",
                    "content": point.payload.get("content", ""),
                    "ref_date": ref_date,
                    "metadata": point.payload.get("metadata", {})
                }

                if ref_date == target_date:
                    result["day2"].append(doc)
                elif prev_date and ref_date == prev_date:
                    result["day1"].append(doc)
                elif next_date and ref_date == next_date:
                    result["day3"].append(doc)

        except Exception as e:
            logger.error(f"Error retrieving notion documents: {e}")

        return result

    def _retrieve_naver_by_dates(
        self, target_date: str, prev_date: str | None, next_date: str | None
    ) -> dict[str, list]:
        """Naver 문서를 날짜로 검색합니다 (Python 필터링 사용)."""
        result = {"day1": [], "day2": [], "day3": []}

        try:
            # 모든 문서 가져오기
            all_results = connection.scroll(
                collection_name="embedded_naver",
                limit=1000
            )

            # Python에서 날짜별로 필터링
            for point in all_results[0]:
                ref_date = point.payload.get("ref_date", "")

                doc = {
                    "source": "naver",
                    "content": point.payload.get("content", ""),
                    "ref_date": ref_date,
                    "metadata": point.payload.get("metadata", {})
                }

                if ref_date == target_date:
                    result["day2"].append(doc)
                elif prev_date and ref_date == prev_date:
                    result["day1"].append(doc)
                elif next_date and ref_date == next_date:
                    result["day3"].append(doc)

        except Exception as e:
            logger.error(f"Error retrieving naver documents: {e}")

        return result
