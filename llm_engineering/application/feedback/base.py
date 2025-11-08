"""
Base class for all feedback generators.

모든 피드백 생성기(daily, weekly, monthly)가 공통으로 사용하는 추상 클래스입니다.
"""

from abc import ABC, abstractmethod
from typing import Optional

from langchain_openai import ChatOpenAI
from loguru import logger

from llm_engineering.settings import Settings

# Load settings singleton
settings = Settings.load_settings()


class BaseFeedbackGenerator(ABC):
    """
    피드백 생성기의 기본 클래스.

    공통 기능:
    - LLM 초기화 및 관리
    - 문서 포맷팅
    - 에러 핸들링
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize the feedback generator.

        Args:
            model_id: LLM model ID (기본: settings.OPENAI_MODEL_ID)
            temperature: LLM temperature (0.0-1.0)
        """
        self.model_id = model_id or settings.OPENAI_MODEL_ID
        self.temperature = temperature

        # LLM 초기화
        self.llm = ChatOpenAI(
            model=self.model_id,
            temperature=self.temperature,
            api_key=settings.OPENAI_API_KEY,
        )

        logger.info(
            f"{self.__class__.__name__} initialized with "
            f"model={self.model_id}, temperature={self.temperature}"
        )

    @abstractmethod
    def generate(self, **kwargs) -> str:
        """
        피드백을 생성합니다.

        각 서브클래스에서 구현해야 합니다.

        Returns:
            생성된 피드백 문자열
        """
        pass

    def _format_document(self, doc: dict, include_metadata: bool = False) -> str:
        """
        단일 문서를 포맷팅합니다.

        Args:
            doc: CleanedDocument.model_dump() 결과
            include_metadata: 메타데이터 포함 여부

        Returns:
            포맷팅된 문서 문자열
        """
        platform = doc.get("platform", "unknown").upper()
        ref_date = doc.get("ref_date", "N/A")
        content = doc.get("content", "")

        parts = [f"### [{platform}] {ref_date}", content]

        if include_metadata:
            metadata = doc.get("metadata", {})
            if metadata:
                parts.append(f"\n**메타데이터**: {metadata}")

        return "\n".join(parts)

    def _format_documents(
        self, docs: list[dict], title: str = "문서", include_metadata: bool = False
    ) -> str:
        """
        여러 문서를 포맷팅합니다.

        Args:
            docs: 문서 리스트
            title: 섹션 제목
            include_metadata: 메타데이터 포함 여부

        Returns:
            포맷팅된 문서 문자열
        """
        if not docs:
            return f"## {title}\n\n해당 기간의 데이터를 찾을 수 없습니다.\n"

        parts = [f"## {title}", ""]

        for doc in docs:
            parts.append(self._format_document(doc, include_metadata))
            parts.append("")  # 문서 간 구분

        return "\n".join(parts)

    def _count_documents(self, docs: list[dict]) -> dict[str, int]:
        """
        플랫폼별 문서 수를 계산합니다.

        Args:
            docs: 문서 리스트

        Returns:
            플랫폼별 카운트 딕셔너리
        """
        counts = {}
        for doc in docs:
            platform = doc.get("platform", "unknown")
            counts[platform] = counts.get(platform, 0) + 1
        return counts
