"""
Embedding data handlers for converting CleanedDocuments to EmbeddedDocuments.

CleanedDocument → EmbeddingHandler → EmbeddedDocument (with vector)
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, cast

import tiktoken
from loguru import logger

from llm_engineering.application.networks.embeddings import EmbeddingModelSingleton
from llm_engineering.domain.cleaned_documents import (
    CleanedCalendarDocument,
    CleanedNotionDocument,
    CleanedNaverDocument,
)
from llm_engineering.domain.embedded_documents import (
    EmbeddedCalendarDocument,
    EmbeddedNotionDocument,
    EmbeddedNaverDocument,
    EmbeddedDocument,
)

CleanedDocT = TypeVar("CleanedDocT")
EmbeddedDocT = TypeVar("EmbeddedDocT", bound=EmbeddedDocument)

# Initialize singleton embedding model
embedding_model = EmbeddingModelSingleton()

# Initialize tokenizer for truncation
tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4/GPT-3.5-turbo encoding


class EmbeddingDataHandler(ABC, Generic[CleanedDocT, EmbeddedDocT]):
    """
    Abstract base class for embedding data handlers.

    CleanedDocument를 받아서 임베딩을 생성하고 EmbeddedDocument로 변환합니다.
    """

    def embed(self, data_model: CleanedDocT) -> EmbeddedDocT:
        """
        단일 문서를 임베딩합니다.

        Args:
            data_model: 임베딩할 CleanedDocument

        Returns:
            임베딩된 EmbeddedDocument
        """
        return self.embed_batch([data_model])[0]

    def embed_batch(
        self, data_models: list[CleanedDocT], batch_size: int = 100, max_tokens: int = 8000
    ) -> list[EmbeddedDocT]:
        """
        여러 문서를 배치로 임베딩합니다.

        Args:
            data_models: 임베딩할 CleanedDocument 리스트
            batch_size: API 호출당 처리할 문서 수 (기본: 100)
            max_tokens: 단일 문서의 최대 토큰 수 (기본: 8000, OpenAI limit: 8191)

        Returns:
            임베딩된 EmbeddedDocument 리스트
        """
        all_embedded_docs = []

        # 배치 단위로 처리
        for i in range(0, len(data_models), batch_size):
            batch = data_models[i : i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1}/{(len(data_models) + batch_size - 1) // batch_size} "
                f"({len(batch)} documents)"
            )

            # 1. content 추출 및 토큰 제한 처리
            embedding_model_input = []
            for doc in batch:
                content = doc.content
                # 토큰 수 체크 및 truncate
                tokens = tokenizer.encode(content)
                if len(tokens) > max_tokens:
                    logger.warning(
                        f"Document {doc.id} has {len(tokens)} tokens, truncating to {max_tokens}"
                    )
                    tokens = tokens[:max_tokens]
                    content = tokenizer.decode(tokens)

                embedding_model_input.append(content)

            # 2. 임베딩 생성
            embeddings = embedding_model(embedding_model_input, to_list=True)

            # 3. EmbeddedDocument로 변환
            embedded_docs = [
                self.map_model(doc, cast(list[float], embedding))
                for doc, embedding in zip(batch, embeddings, strict=False)
            ]

            all_embedded_docs.extend(embedded_docs)

        return all_embedded_docs

    @abstractmethod
    def map_model(self, data_model: CleanedDocT, embedding: list[float]) -> EmbeddedDocT:
        """
        CleanedDocument + embedding을 EmbeddedDocument로 매핑합니다.

        Args:
            data_model: CleanedDocument
            embedding: 벡터 임베딩

        Returns:
            EmbeddedDocument
        """
        pass


class CalendarEmbeddingHandler(EmbeddingDataHandler):
    """Calendar 문서용 임베딩 핸들러"""

    def map_model(
        self, data_model: CleanedCalendarDocument, embedding: list[float]
    ) -> EmbeddedCalendarDocument:
        """
        CleanedCalendarDocument를 EmbeddedCalendarDocument로 변환합니다.

        Args:
            data_model: CleanedCalendarDocument
            embedding: 벡터 임베딩

        Returns:
            EmbeddedCalendarDocument
        """
        # metadata에 임베딩 모델 정보 추가
        metadata = data_model.metadata.copy()
        metadata.update(
            {
                "embedding_model_id": embedding_model.model_id,
                "embedding_size": embedding_model.embedding_size,
                "max_input_length": embedding_model.max_input_length,
            }
        )

        return EmbeddedCalendarDocument(
            original_id=data_model.id,  # CleanedDocument의 ID
            content=data_model.content,
            embedding=embedding,
            ref_date=data_model.ref_date,
            platform=data_model.platform,
            doc_type=data_model.doc_type,
            author_id=data_model.author_id,
            author_full_name=data_model.author_full_name,
            metadata=metadata,
        )


class NotionEmbeddingHandler(EmbeddingDataHandler):
    """Notion 문서용 임베딩 핸들러"""

    def map_model(
        self, data_model: CleanedNotionDocument, embedding: list[float]
    ) -> EmbeddedNotionDocument:
        """
        CleanedNotionDocument를 EmbeddedNotionDocument로 변환합니다.

        Args:
            data_model: CleanedNotionDocument
            embedding: 벡터 임베딩

        Returns:
            EmbeddedNotionDocument
        """
        metadata = data_model.metadata.copy()
        metadata.update(
            {
                "embedding_model_id": embedding_model.model_id,
                "embedding_size": embedding_model.embedding_size,
                "max_input_length": embedding_model.max_input_length,
            }
        )

        return EmbeddedNotionDocument(
            original_id=data_model.id,
            content=data_model.content,
            embedding=embedding,
            ref_date=data_model.ref_date,
            platform=data_model.platform,
            doc_type=data_model.doc_type,
            author_id=data_model.author_id,
            author_full_name=data_model.author_full_name,
            metadata=metadata,
        )


class NaverEmbeddingHandler(EmbeddingDataHandler):
    """Naver 블로그용 임베딩 핸들러"""

    def map_model(
        self, data_model: CleanedNaverDocument, embedding: list[float]
    ) -> EmbeddedNaverDocument:
        """
        CleanedNaverDocument를 EmbeddedNaverDocument로 변환합니다.

        Args:
            data_model: CleanedNaverDocument
            embedding: 벡터 임베딩

        Returns:
            EmbeddedNaverDocument
        """
        metadata = data_model.metadata.copy()
        metadata.update(
            {
                "embedding_model_id": embedding_model.model_id,
                "embedding_size": embedding_model.embedding_size,
                "max_input_length": embedding_model.max_input_length,
            }
        )

        return EmbeddedNaverDocument(
            original_id=data_model.id,
            content=data_model.content,
            embedding=embedding,
            ref_date=data_model.ref_date,
            platform=data_model.platform,
            doc_type=data_model.doc_type,
            author_id=data_model.author_id,
            author_full_name=data_model.author_full_name,
            metadata=metadata,
        )
