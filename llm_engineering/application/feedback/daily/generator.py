"""
Daily Feedback Generator.

3일 윈도우 (전날, 당일, 다음날)를 사용하여 일일 피드백을 생성합니다.
"""

from contextlib import nullcontext
from typing import Optional

from langchain.prompts import ChatPromptTemplate
from langchain_core.tracers.context import tracing_v2_enabled
from loguru import logger

from llm_engineering.domain.feedback_documents import DailyFeedbackDocument
from llm_engineering.settings import Settings
from ..base import BaseFeedbackGenerator
from ..document_loader import DocumentLoader
from .prompts import get_prompt

# Load settings singleton
settings = Settings.load_settings()


class DailyFeedbackGenerator(BaseFeedbackGenerator):
    """
    일일 피드백 생성기.

    특징:
    - 3일 윈도우: 전날 Calendar (저녁), 당일 모든 소스, 다음날 Calendar (아침)
    - In-context: 해당 기간의 모든 문서를 컨텍스트로 사용
    - 다양한 프롬프트 스타일 지원
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        prompt_style: str = "original",
    ):
        """
        Initialize the daily feedback generator.

        Args:
            model_id: LLM model ID
            temperature: LLM temperature
            prompt_style: 프롬프트 스타일 (original, minimal, coach, scientist, cbt, narrative, dashboard, metacognitive)
        """
        super().__init__(model_id, temperature)
        self.prompt_style = prompt_style
        self.system_prompt = get_prompt(prompt_style)

        logger.info(f"DailyFeedbackGenerator initialized with style={prompt_style}")

    def generate(
        self,
        target_date: str,
        author_full_name: Optional[str] = None,
        include_previous: bool = True,
        include_next: bool = True,
        additional_context: Optional[str] = None,
        save_to_db: bool = False,
    ) -> str:
        """
        일일 피드백을 생성합니다.

        Args:
            target_date: 분석 대상 날짜 (YYYY-MM-DD)
            author_full_name: 작성자 이름 (선택사항)
            include_previous: 전날 포함 여부
            include_next: 다음날 포함 여부
            additional_context: 추가 컨텍스트 (선택사항)

        Returns:
            생성된 피드백 문자열
        """
        logger.info(f"Generating daily feedback for {target_date}")

        # 1. 문서 로드 (3일 윈도우)
        docs = DocumentLoader.load_with_context(
            target_date=target_date,
            include_previous=include_previous,
            include_next=include_next,
            author_full_name=author_full_name,
        )

        # 2. 문서 포맷팅
        context = self._format_3day_context(
            docs, target_date, include_previous, include_next
        )

        if additional_context:
            context += f"\n\n## 추가 컨텍스트\n{additional_context}"

        # 3. 통계 로깅
        self._log_statistics(docs, target_date)

        # 4. LLM 호출
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
                f"Daily feedback generated successfully ({len(feedback)} chars)"
            )

            # MongoDB에 저장
            if save_to_db:
                self._save_feedback(
                    target_date=target_date,
                    feedback=feedback,
                    author_full_name=author_full_name,
                    include_previous=include_previous,
                    include_next=include_next,
                    stats=self._get_generation_stats(docs),
                )

            return feedback

        except Exception as e:
            logger.error(f"Error generating daily feedback: {e}")
            raise

    def _format_3day_context(
        self,
        docs: dict[str, list[dict]],
        target_date: str,
        include_previous: bool,
        include_next: bool,
    ) -> str:
        """
        3일 윈도우 문서를 LLM 입력 형식으로 포맷팅합니다.

        Args:
            docs: load_with_context() 결과
            target_date: 분석 대상 날짜
            include_previous: 전날 포함 여부
            include_next: 다음날 포함 여부

        Returns:
            포맷팅된 컨텍스트 문자열
        """
        context_parts = []

        # Day 1 (전날): Calendar만
        if include_previous and docs.get("previous"):
            context_parts.append("## [Day 1: Context] 전날 저녁 활동 (Calendar)")
            context_parts.append("")
            context_parts.append(
                self._format_documents(
                    docs["previous"],
                    title="",
                    include_metadata=False
                )
            )

        # Day 2 (당일): 모든 소스
        if docs.get("target"):
            context_parts.append(
                f"## [Day 2: Target Date] 분석 대상일: {target_date}"
            )
            context_parts.append("")
            context_parts.append(
                self._format_documents(
                    docs["target"],
                    title="",
                    include_metadata=False
                )
            )
        else:
            context_parts.append(f"## [Day 2: Target Date] {target_date}")
            context_parts.append("")
            context_parts.append("해당 날짜의 데이터를 찾을 수 없습니다.")

        # Day 3 (다음날): Calendar만
        if include_next and docs.get("next"):
            context_parts.append("## [Day 3: Context] 다음날 아침 활동 (Calendar)")
            context_parts.append("")
            context_parts.append(
                self._format_documents(
                    docs["next"],
                    title="",
                    include_metadata=False
                )
            )

        return "\n".join(context_parts)

    def _log_statistics(self, docs: dict[str, list[dict]], target_date: str):
        """
        로드된 문서 통계를 로깅합니다.

        Args:
            docs: load_with_context() 결과
            target_date: 분석 대상 날짜
        """
        stats = {
            "target_date": target_date,
            "previous": len(docs.get("previous", [])),
            "target": len(docs.get("target", [])),
            "next": len(docs.get("next", [])),
            "total": (
                len(docs.get("previous", []))
                + len(docs.get("target", []))
                + len(docs.get("next", []))
            ),
        }

        # 당일 문서 플랫폼별 통계
        if docs.get("target"):
            target_counts = self._count_documents(docs["target"])
            stats["target_by_platform"] = target_counts

        logger.info(f"Document statistics: {stats}")

    def set_prompt_style(self, style: str):
        """
        프롬프트 스타일을 변경합니다.

        Args:
            style: 새로운 프롬프트 스타일
        """
        self.prompt_style = style
        self.system_prompt = get_prompt(style)
        logger.info(f"Prompt style changed to: {style}")

    def _save_feedback(
        self,
        target_date: str,
        feedback: str,
        author_full_name: Optional[str],
        include_previous: bool,
        include_next: bool,
        stats: dict,
    ):
        """
        생성된 피드백을 MongoDB에 저장합니다.

        Args:
            target_date: 대상 날짜
            feedback: 생성된 피드백 내용
            author_full_name: 작성자 이름
            include_previous: 전날 포함 여부
            include_next: 다음날 포함 여부
            stats: 생성 통계
        """
        feedback_doc = DailyFeedbackDocument(
            target_date=target_date,
            content=feedback,
            model_used=self.model_id,
            temperature=self.temperature,
            author_full_name=author_full_name,
            prompt_style=self.prompt_style,
            include_previous=include_previous,
            include_next=include_next,
            stats=stats,
        )

        feedback_doc.save()
        logger.info(f"Daily feedback saved to MongoDB: {feedback_doc.id}")

    def _get_generation_stats(self, docs: dict[str, list[dict]]) -> dict:
        """
        생성 시 사용된 문서 통계를 계산합니다.

        Args:
            docs: load_with_context() 결과

        Returns:
            통계 딕셔너리
        """
        total_docs = (
            len(docs.get("previous", []))
            + len(docs.get("target", []))
            + len(docs.get("next", []))
        )

        by_platform = {}
        for day_docs in docs.values():
            for doc in day_docs:
                platform = doc.get("platform", "unknown")
                by_platform[platform] = by_platform.get(platform, 0) + 1

        return {
            "total_docs": total_docs,
            "previous_docs": len(docs.get("previous", [])),
            "target_docs": len(docs.get("target", [])),
            "next_docs": len(docs.get("next", [])),
            "by_platform": by_platform,
        }
