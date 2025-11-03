"""
Feedback Generation Chain using LangChain.

RAG 검색 결과를 기반으로 LLM 피드백을 생성합니다.
"""

from typing import Literal

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger

from llm_engineering.application.prompts.feedback_prompts import get_prompt
from llm_engineering.settings import settings


class FeedbackChain:
    """
    RAG 기반 피드백 생성 체인.

    검색된 문서를 컨텍스트로 LLM에게 전달하여 피드백을 생성합니다.
    """

    def __init__(
        self,
        model_id: str = None,
        temperature: float = 0.7,
        prompt_style: Literal[
            "original", "minimal", "coach", "scientist", "cbt", "narrative", "dashboard", "metacognitive"
        ] = "original"
    ):
        """
        Initialize the feedback chain.

        Args:
            model_id: LLM model ID (기본: settings.OPENAI_MODEL_ID)
            temperature: LLM temperature (0.0-1.0)
            prompt_style: 피드백 프롬프트 스타일
        """
        self.model_id = model_id or settings.OPENAI_MODEL_ID
        self.temperature = temperature
        self.prompt_style = prompt_style

        # LLM 초기화
        self.llm = ChatOpenAI(
            model=self.model_id,
            temperature=self.temperature,
            api_key=settings.OPENAI_API_KEY
        )

        # System prompt 로드
        self.system_prompt = get_prompt(prompt_style)

        logger.info(
            f"FeedbackChain initialized with model={self.model_id}, "
            f"temperature={self.temperature}, style={self.prompt_style}"
        )

    def generate_feedback(
        self,
        retrieved_docs: dict[str, list],
        target_date: str,
        additional_context: str | None = None
    ) -> str:
        """
        검색된 문서를 기반으로 피드백을 생성합니다.

        Args:
            retrieved_docs: DocumentRetriever.retrieve_by_date_range()의 결과
                {
                    "day1": [...],  # 전날 문서
                    "day2": [...],  # 분석 대상일 문서
                    "day3": [...]   # 다음날 문서
                }
            target_date: 분석 대상 날짜 (YYYY-MM-DD)
            additional_context: 추가 컨텍스트 (선택사항)

        Returns:
            생성된 피드백 문자열
        """
        logger.info(f"Generating feedback for {target_date}")

        # 문서 포맷팅
        context = self._format_documents(retrieved_docs, target_date)

        if additional_context:
            context += f"\n\n## 추가 컨텍스트\n{additional_context}"

        # Prompt 구성
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{context}")
        ])

        # Chain 실행
        chain = prompt | self.llm

        try:
            response = chain.invoke({"context": context})
            feedback = response.content

            logger.info(f"Feedback generated successfully ({len(feedback)} chars)")
            return feedback

        except Exception as e:
            logger.error(f"Error generating feedback: {e}")
            raise

    def _format_documents(self, retrieved_docs: dict[str, list], target_date: str) -> str:
        """
        검색된 문서를 LLM 입력 형식으로 포맷팅합니다.

        Args:
            retrieved_docs: 검색된 문서 딕셔너리
            target_date: 분석 대상 날짜

        Returns:
            포맷팅된 컨텍스트 문자열
        """
        context_parts = []

        # Day 1 (전날)
        if retrieved_docs.get("day1"):
            context_parts.append("## [Day 1: Context] 전날 데이터")
            context_parts.append("")
            for doc in retrieved_docs["day1"]:
                source = doc.get("source", "unknown").upper()
                ref_date = doc.get("ref_date", "N/A")
                content = doc.get("content", "")
                context_parts.append(f"### [{source}] {ref_date}")
                context_parts.append(content)
                context_parts.append("")

        # Day 2 (분석 대상일)
        if retrieved_docs.get("day2"):
            context_parts.append(f"## [Day 2: Target Date] 분석 대상일: {target_date}")
            context_parts.append("")
            for doc in retrieved_docs["day2"]:
                source = doc.get("source", "unknown").upper()
                ref_date = doc.get("ref_date", "N/A")
                content = doc.get("content", "")
                context_parts.append(f"### [{source}] {ref_date}")
                context_parts.append(content)
                context_parts.append("")

        # Day 3 (다음날)
        if retrieved_docs.get("day3"):
            context_parts.append("## [Day 3: Context] 다음날 데이터")
            context_parts.append("")
            for doc in retrieved_docs["day3"]:
                source = doc.get("source", "unknown").upper()
                ref_date = doc.get("ref_date", "N/A")
                content = doc.get("content", "")
                context_parts.append(f"### [{source}] {ref_date}")
                context_parts.append(content)
                context_parts.append("")

        # 문서가 없을 경우
        if not context_parts:
            context_parts.append(f"## {target_date} 데이터")
            context_parts.append("")
            context_parts.append("해당 날짜의 데이터를 찾을 수 없습니다.")

        return "\n".join(context_parts)

    def set_prompt_style(
        self,
        style: Literal[
            "original", "minimal", "coach", "scientist", "cbt", "narrative", "dashboard", "metacognitive"
        ]
    ):
        """
        프롬프트 스타일을 변경합니다.

        Args:
            style: 새로운 프롬프트 스타일
        """
        self.prompt_style = style
        self.system_prompt = get_prompt(style)
        logger.info(f"Prompt style changed to: {style}")

    def get_available_styles(self) -> dict:
        """사용 가능한 프롬프트 스타일 정보를 반환합니다."""
        from llm_engineering.application.prompts.feedback_prompts import PROMPTS_REGISTRY
        return PROMPTS_REGISTRY
