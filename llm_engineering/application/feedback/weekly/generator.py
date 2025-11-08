"""
Weekly Feedback Generator.

7일간의 데이터를 분석하여 주간 피드백을 생성합니다.
"""

from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import Optional

from langchain.prompts import ChatPromptTemplate
from langchain_core.tracers.context import tracing_v2_enabled
from loguru import logger

from llm_engineering.domain.feedback_documents import WeeklyFeedbackDocument
from llm_engineering.settings import Settings
from ..base import BaseFeedbackGenerator
from ..document_loader import DocumentLoader
from .prompts import WEEKLY_FEEDBACK_PROMPT

# Load settings singleton
settings = Settings.load_settings()


class WeeklyFeedbackGenerator(BaseFeedbackGenerator):
    """
    주간 피드백 생성기.

    특징:
    - 7일간의 모든 데이터 in-context 로드
    - 과거 주간 리포트 참조 (Notion)
    - 패턴 분석 중심
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize the weekly feedback generator.

        Args:
            model_id: LLM model ID
            temperature: LLM temperature
        """
        super().__init__(model_id, temperature)
        self.system_prompt = WEEKLY_FEEDBACK_PROMPT

        logger.info("WeeklyFeedbackGenerator initialized")

    def generate(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        author_full_name: Optional[str] = None,
        include_past_reports: bool = True,
        past_reports_limit: int = 4,
        additional_context: Optional[str] = None,
        save_to_db: bool = False,
    ) -> str:
        """
        주간 피드백을 생성합니다.

        Args:
            start_date: 주 시작 날짜 (YYYY-MM-DD, 월요일 권장)
            end_date: 주 종료 날짜 (YYYY-MM-DD, 선택사항, 기본: start_date + 6일)
            author_full_name: 작성자 이름 (선택사항)
            include_past_reports: 과거 주간 리포트 포함 여부
            past_reports_limit: 과거 주간 리포트 최대 개수
            additional_context: 추가 컨텍스트 (선택사항)

        Returns:
            생성된 주간 피드백 문자열
        """
        # 종료일 계산
        if end_date is None:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=6)
            end_date = end_dt.strftime("%Y-%m-%d")

        logger.info(f"Generating weekly feedback for {start_date} ~ {end_date}")

        # 1. 7일 데이터 로드
        weekly_docs = DocumentLoader.load_by_date_range(
            start_date=start_date,
            end_date=end_date,
            sources=["calendar", "notion", "naver_blog"],
            author_full_name=author_full_name,
            include_weekly_reports=False,  # 이번 주 리포트는 제외
        )

        # 2. 과거 주간 리포트 로드 (컨텍스트용)
        past_reports = []
        if include_past_reports:
            past_reports = DocumentLoader.load_weekly_reports(
                start_date=self._get_past_week_start(start_date, weeks_back=8),
                end_date=start_date,  # 이번 주 시작 전까지
                author_full_name=author_full_name,
                limit=past_reports_limit,
            )

        # 3. 컨텍스트 포맷팅
        context = self._format_weekly_context(
            start_date, end_date, weekly_docs, past_reports
        )

        if additional_context:
            context += f"\n\n## 추가 컨텍스트\n{additional_context}"

        # 4. 통계 로깅
        self._log_statistics(start_date, end_date, weekly_docs, past_reports)

        # 5. LLM 호출
        prompt = ChatPromptTemplate.from_messages(
            [("system", self.system_prompt), ("human", "{context}")]
        )

        chain = prompt | self.llm

        try:
            # LangSmith 추적 활성화
            if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
                import os
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT

            response = chain.invoke({"context": context})
            feedback = response.content

            logger.info(
                f"Weekly feedback generated successfully ({len(feedback)} chars)"
            )
            return feedback

        except Exception as e:
            logger.error(f"Error generating weekly feedback: {e}")
            raise

    def _format_weekly_context(
        self,
        start_date: str,
        end_date: str,
        weekly_docs: list[dict],
        past_reports: list[dict],
    ) -> str:
        """
        주간 데이터를 LLM 입력 형식으로 포맷팅합니다.

        Args:
            start_date: 주 시작 날짜
            end_date: 주 종료 날짜
            weekly_docs: 이번 주 7일 데이터
            past_reports: 과거 주간 리포트

        Returns:
            포맷팅된 컨텍스트 문자열
        """
        context_parts = []

        # 주간 정보
        context_parts.append(f"## 주간 분석 대상: {start_date} ~ {end_date}")
        context_parts.append("")

        # 이번 주 데이터
        if weekly_docs:
            # 날짜별로 그룹화
            docs_by_date = self._group_by_date(weekly_docs)

            context_parts.append("## 이번 주 데이터 (일별)")
            context_parts.append("")

            for date in sorted(docs_by_date.keys()):
                day_docs = docs_by_date[date]
                day_name = self._get_day_name(date)

                context_parts.append(f"### {date} ({day_name})")
                context_parts.append("")

                for doc in day_docs:
                    context_parts.append(self._format_document(doc))
                    context_parts.append("")
        else:
            context_parts.append("## 이번 주 데이터")
            context_parts.append("")
            context_parts.append("해당 기간의 데이터를 찾을 수 없습니다.")
            context_parts.append("")

        # 과거 주간 리포트
        if past_reports:
            context_parts.append("## 과거 주간 리포트 (참고용)")
            context_parts.append("")

            for report in past_reports:
                week_start = report.get("metadata", {}).get("week_start_date", "N/A")
                week_end = report.get("metadata", {}).get("week_end_date", "N/A")
                title = report.get("metadata", {}).get("title", "주간 리포트")

                context_parts.append(f"### {title} ({week_start} ~ {week_end})")
                context_parts.append("")
                context_parts.append(report.get("content", ""))
                context_parts.append("")
                context_parts.append("---")
                context_parts.append("")

        return "\n".join(context_parts)

    def _group_by_date(self, docs: list[dict]) -> dict[str, list[dict]]:
        """
        문서를 ref_date 기준으로 그룹화합니다.

        Args:
            docs: 문서 리스트

        Returns:
            날짜별 문서 딕셔너리
        """
        grouped = {}
        for doc in docs:
            ref_date = doc.get("ref_date", "unknown")
            if ref_date not in grouped:
                grouped[ref_date] = []
            grouped[ref_date].append(doc)
        return grouped

    def _get_day_name(self, date_str: str) -> str:
        """
        날짜 문자열을 요일명으로 변환합니다.

        Args:
            date_str: YYYY-MM-DD 형식 날짜

        Returns:
            요일명 (예: "월요일")
        """
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
            return days[date_obj.weekday()]
        except Exception:
            return ""

    def _get_past_week_start(self, current_week_start: str, weeks_back: int = 8) -> str:
        """
        과거 N주 전의 시작 날짜를 계산합니다.

        Args:
            current_week_start: 현재 주 시작 날짜
            weeks_back: 몇 주 전부터

        Returns:
            과거 주 시작 날짜 (YYYY-MM-DD)
        """
        date_obj = datetime.strptime(current_week_start, "%Y-%m-%d")
        past_date = date_obj - timedelta(weeks=weeks_back)
        return past_date.strftime("%Y-%m-%d")

    def _log_statistics(
        self,
        start_date: str,
        end_date: str,
        weekly_docs: list[dict],
        past_reports: list[dict],
    ):
        """
        로드된 문서 통계를 로깅합니다.

        Args:
            start_date: 주 시작 날짜
            end_date: 주 종료 날짜
            weekly_docs: 주간 문서 리스트
            past_reports: 과거 주간 리포트 리스트
        """
        stats = {
            "week": f"{start_date} ~ {end_date}",
            "total_docs": len(weekly_docs),
            "past_reports": len(past_reports),
        }

        # 플랫폼별 통계
        if weekly_docs:
            stats["by_platform"] = self._count_documents(weekly_docs)

        # 날짜별 통계
        docs_by_date = self._group_by_date(weekly_docs)
        stats["by_date"] = {date: len(docs) for date, docs in docs_by_date.items()}

        logger.info(f"Weekly statistics: {stats}")
