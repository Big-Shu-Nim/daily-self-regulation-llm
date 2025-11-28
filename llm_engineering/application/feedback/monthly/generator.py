"""
Monthly Feedback Generator.

30일간의 데이터를 계층적으로 요약하여 월간 피드백을 생성합니다.
"""

from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import Optional

from langchain.prompts import ChatPromptTemplate
from langchain_core.tracers.context import tracing_v2_enabled
from loguru import logger

from llm_engineering.settings import Settings
from ..base import BaseFeedbackGenerator
from ..document_loader import DocumentLoader
from .prompts import (
    MONTHLY_FEEDBACK_PROMPT,
    MONTHLY_FEEDBACK_PROMPT_PUBLIC,
    MONTHLY_SUMMARY_PROMPT,
    MONTHLY_SUMMARY_PROMPT_PUBLIC,
)

# Load settings singleton
settings = Settings.load_settings()


class MonthlyFeedbackGenerator(BaseFeedbackGenerator):
    """
    월간 피드백 생성기.

    특징:
    - 계층적 요약 전략: 주별 요약 → 월간 피드백
    - 30일 데이터를 4-5주로 분할하여 처리
    - 장기 트렌드 및 반복 패턴 분석
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        prompt_style: str = "original",
    ):
        """
        Initialize the monthly feedback generator.

        Args:
            model_id: LLM model ID
            temperature: LLM temperature
            prompt_style: 프롬프트 스타일 ("original", "public")
        """
        super().__init__(model_id, temperature)
        self.prompt_style = prompt_style

        # Select prompts based on style
        if prompt_style == "public":
            self.summary_prompt = MONTHLY_SUMMARY_PROMPT_PUBLIC
            self.feedback_prompt = MONTHLY_FEEDBACK_PROMPT_PUBLIC
        else:
            self.summary_prompt = MONTHLY_SUMMARY_PROMPT
            self.feedback_prompt = MONTHLY_FEEDBACK_PROMPT

        logger.info(f"MonthlyFeedbackGenerator initialized (style={prompt_style})")

    def generate(
        self,
        year: int,
        month: int,
        author_full_name: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> str:
        """
        월간 피드백을 생성합니다.

        Args:
            year: 연도 (YYYY)
            month: 월 (1-12)
            author_full_name: 작성자 이름 (선택사항)
            additional_context: 추가 컨텍스트 (선택사항)

        Returns:
            생성된 월간 피드백 문자열
        """
        import asyncio

        logger.info(f"Generating monthly feedback for {year}-{month:02d}")

        # 1. 월의 시작일과 종료일 계산
        start_date, end_date = self._get_month_range(year, month)

        # 2. 주별로 데이터 분할
        weeks = self._split_into_weeks(start_date, end_date)

        # 3. 각 주별 요약 생성 (병렬 처리)
        weekly_summaries = asyncio.run(
            self._generate_weekly_summaries_async(weeks, author_full_name)
        )

        # 4. 주간 요약들을 종합하여 월간 피드백 생성 (2단계)
        monthly_feedback = self._generate_monthly_feedback(
            year=year,
            month=month,
            weekly_summaries=weekly_summaries,
            additional_context=additional_context,
        )

        logger.info(
            f"Monthly feedback generated successfully ({len(monthly_feedback)} chars)"
        )
        return monthly_feedback

    async def _generate_weekly_summaries_async(
        self,
        weeks: list[tuple[str, str]],
        author_full_name: Optional[str],
    ) -> list[str]:
        """
        주간 요약들을 비동기로 병렬 생성합니다.

        Args:
            weeks: [(week_start, week_end), ...] 리스트
            author_full_name: 작성자 이름

        Returns:
            주간 요약 리스트
        """
        import asyncio

        tasks = [
            self._generate_weekly_summary_async(
                week_num=week_num,
                week_start=week_start,
                week_end=week_end,
                author_full_name=author_full_name,
            )
            for week_num, (week_start, week_end) in enumerate(weeks, 1)
        ]

        logger.info(f"Starting parallel generation of {len(tasks)} weekly summaries")
        summaries = await asyncio.gather(*tasks)
        logger.info(f"Completed parallel generation of {len(summaries)} weekly summaries")

        return summaries

    async def _generate_weekly_summary_async(
        self,
        week_num: int,
        week_start: str,
        week_end: str,
        author_full_name: Optional[str],
    ) -> str:
        """
        특정 주의 데이터를 비동기로 요약합니다.

        Args:
            week_num: 주 번호 (1, 2, 3, ...)
            week_start: 주 시작 날짜
            week_end: 주 종료 날짜
            author_full_name: 작성자 이름

        Returns:
            주간 요약 문자열
        """
        logger.info(f"Generating summary for Week {week_num}: {week_start} ~ {week_end}")

        # 주간 데이터 로드
        weekly_docs = DocumentLoader.load_by_date_range(
            start_date=week_start,
            end_date=week_end,
            sources=["calendar", "notion", "naver_blog"],
            author_full_name=author_full_name,
            include_weekly_reports=False,
        )

        # 컨텍스트 포맷팅
        context = self._format_week_data(week_num, week_start, week_end, weekly_docs)

        # LLM 호출 (비동기)
        prompt = ChatPromptTemplate.from_messages(
            [("system", self.summary_prompt), ("human", "{context}")]
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

            response = await chain.ainvoke({"context": context})
            summary = response.content

            logger.debug(f"Week {week_num} summary generated ({len(summary)} chars)")
            return summary

        except Exception as e:
            logger.error(f"Error generating week {week_num} summary: {e}")
            # 실패 시 기본 요약 반환
            return f"### Week {week_num}: {week_start} ~ {week_end}\n\n데이터 요약 실패.\n\n---\n"

    def _get_month_range(self, year: int, month: int) -> tuple[str, str]:
        """
        월의 시작일과 종료일을 계산합니다.

        Args:
            year: 연도
            month: 월

        Returns:
            (start_date, end_date) tuple (YYYY-MM-DD 형식)
        """
        start_date = datetime(year, month, 1)

        # 다음 달 1일에서 하루 빼기
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)

        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    def _split_into_weeks(
        self, start_date: str, end_date: str
    ) -> list[tuple[str, str]]:
        """
        월을 주별로 분할합니다 (월요일 시작 기준).

        Args:
            start_date: 월 시작 날짜
            end_date: 월 종료 날짜

        Returns:
            [(week1_start, week1_end), (week2_start, week2_end), ...]
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        weeks = []
        current = start_dt

        while current <= end_dt:
            # 이번 주 월요일 찾기
            week_start = current - timedelta(days=current.weekday())

            # 이번 주 일요일
            week_end = week_start + timedelta(days=6)

            # 월 범위 내로 제한
            if week_start < start_dt:
                week_start = start_dt
            if week_end > end_dt:
                week_end = end_dt

            weeks.append(
                (week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
            )

            # 다음 주로
            current = week_end + timedelta(days=1)

        return weeks

    def _generate_weekly_summary(
        self,
        week_num: int,
        week_start: str,
        week_end: str,
        author_full_name: Optional[str],
    ) -> str:
        """
        특정 주의 데이터를 요약합니다 (1단계).

        Args:
            week_num: 주 번호 (1, 2, 3, ...)
            week_start: 주 시작 날짜
            week_end: 주 종료 날짜
            author_full_name: 작성자 이름

        Returns:
            주간 요약 문자열
        """
        logger.info(f"Generating summary for Week {week_num}: {week_start} ~ {week_end}")

        # 주간 데이터 로드
        weekly_docs = DocumentLoader.load_by_date_range(
            start_date=week_start,
            end_date=week_end,
            sources=["calendar", "notion", "naver_blog"],
            author_full_name=author_full_name,
            include_weekly_reports=False,
        )

        # 컨텍스트 포맷팅
        context = self._format_week_data(week_num, week_start, week_end, weekly_docs)

        # LLM 호출 (요약)
        prompt = ChatPromptTemplate.from_messages(
            [("system", self.summary_prompt), ("human", "{context}")]
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
            summary = response.content

            logger.debug(f"Week {week_num} summary generated ({len(summary)} chars)")
            return summary

        except Exception as e:
            logger.error(f"Error generating week {week_num} summary: {e}")
            # 실패 시 기본 요약 반환
            return f"### Week {week_num}: {week_start} ~ {week_end}\n\n데이터 요약 실패.\n\n---\n"

    def _generate_monthly_feedback(
        self,
        year: int,
        month: int,
        weekly_summaries: list[str],
        additional_context: Optional[str],
    ) -> str:
        """
        주간 요약들을 종합하여 월간 피드백을 생성합니다 (2단계).

        Args:
            year: 연도
            month: 월
            weekly_summaries: 주간 요약 리스트
            additional_context: 추가 컨텍스트

        Returns:
            월간 피드백 문자열
        """
        logger.info(f"Generating monthly feedback from {len(weekly_summaries)} weekly summaries")

        # 컨텍스트 구성
        context_parts = [f"## 월간 분석 대상: {year}년 {month}월", ""]

        # 주간 요약들
        context_parts.append("## 주별 요약")
        context_parts.append("")
        for summary in weekly_summaries:
            context_parts.append(summary)
            context_parts.append("")

        if additional_context:
            context_parts.append("## 추가 컨텍스트")
            context_parts.append(additional_context)

        context = "\n".join(context_parts)

        # LLM 호출 (월간 피드백)
        prompt = ChatPromptTemplate.from_messages(
            [("system", self.feedback_prompt), ("human", "{context}")]
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

            return feedback

        except Exception as e:
            logger.error(f"Error generating monthly feedback: {e}")
            raise

    def _format_week_data(
        self, week_num: int, week_start: str, week_end: str, docs: list[dict]
    ) -> str:
        """
        주간 데이터를 요약 생성용 형식으로 포맷팅합니다.

        Args:
            week_num: 주 번호
            week_start: 주 시작 날짜
            week_end: 주 종료 날짜
            docs: 주간 문서 리스트

        Returns:
            포맷팅된 컨텍스트 문자열
        """
        context_parts = [
            f"## Week {week_num}: {week_start} ~ {week_end}",
            "",
            f"총 {len(docs)}개 문서",
            "",
        ]

        if not docs:
            context_parts.append("해당 기간의 데이터를 찾을 수 없습니다.")
            return "\n".join(context_parts)

        # 날짜별 그룹화
        docs_by_date = {}
        for doc in docs:
            ref_date = doc.get("ref_date", "unknown")
            if ref_date not in docs_by_date:
                docs_by_date[ref_date] = []
            docs_by_date[ref_date].append(doc)

        # 날짜별 출력 (간결하게)
        for date in sorted(docs_by_date.keys()):
            day_docs = docs_by_date[date]
            context_parts.append(f"### {date}")

            for doc in day_docs:
                # 간결한 포맷
                platform = doc.get("platform", "unknown").upper()
                content = doc.get("content", "")[:200]  # 처음 200자만
                context_parts.append(f"[{platform}] {content}...")
                context_parts.append("")

        return "\n".join(context_parts)
