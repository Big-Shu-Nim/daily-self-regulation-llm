"""
Naver blog data preprocessor.

Naver 블로그 포스트를 전처리합니다.
"""

import re
from typing import List, Dict, Any, Optional

import pandas as pd

from .base import BasePreprocessor
from .utils import flatten_dict_column, clean_text, normalize_date


class NaverPreprocessor(BasePreprocessor):
    """
    Naver 블로그 데이터를 전처리하는 클래스.

    핵심 작업:
    1. content 딕셔너리 필드 평탄화 (title, post_url, published_at, body 추출)
    2. ref_date 추출 (title 또는 published_at에서)
    3. 카테고리별 필터링 (예: 일일피드백만)
    4. 자연어 content 생성 (제목 + 발행일 + 본문)
    """

    def __init__(
        self,
        filter_categories: List[str] = None,
        verbose: bool = True
    ):
        """
        Args:
            filter_categories: 포함할 카테고리 리스트 (예: ['일일피드백'])
                None이면 모든 카테고리 포함
            verbose: 진행 상황 출력 여부
        """
        super().__init__(verbose)
        self.filter_categories = filter_categories

    def clean(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Naver DataFrame을 전처리합니다.

        Args:
            df: 원본 Naver DataFrame

        Returns:
            CleanedNaverDocument에 맞는 dict 리스트
        """
        self.log("="*50)
        self.log(f"Naver 전처리 시작: {len(df)}건")

        # 1. 필수 컬럼 검증
        required_columns = [
            'id', 'content', 'naver_blog_id', 'naver_log_no',
            'link', 'published_at', 'author_id', 'author_full_name'
        ]
        self._validate_dataframe(df, required_columns)

        # 2. content 딕셔너리 평탄화
        df = flatten_dict_column(df.copy(), 'content', drop_original=False)
        self.log("✅ content 필드 평탄화 완료")

        # 3. 카테고리 필터링 (선택적)
        if self.filter_categories:
            df = self._filter_by_categories(df)

        # 4. ref_date 추출
        df = self._extract_ref_dates(df)

        # 5. body_text 정리 (불필요한 헤더 제거)
        df = self._clean_body_text(df)

        # 6. Cleaned documents로 변환
        cleaned_documents = self._to_cleaned_documents(df)

        self.log(f"✅ Naver 전처리 완료: {len(cleaned_documents)}건")
        self.log("="*50)

        return cleaned_documents

    def _filter_by_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """특정 카테고리만 필터링합니다."""
        if 'category' not in df.columns:
            self.log("⚠️ 'category' 컬럼이 없어 필터링 스킵")
            return df

        mask = df['category'].isin(self.filter_categories)
        df_filtered = df[mask].copy()

        self.log(f"📦 카테고리 필터링: {self.filter_categories} → {len(df_filtered)}건 (원본 {len(df)}건)")
        return df_filtered

    def _extract_ref_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        title 또는 published_at에서 ref_date를 추출합니다.

        우선순위:
        1. title에서 날짜 패턴 추출 (예: 20240115_)
        2. published_at에서 날짜 추출 (예: 2024. 1. 15.)
        """
        df['ref_date'] = df.apply(
            lambda row: self._extract_naver_date_ref(
                row.get('title', ''),
                row.get('published_at', '')
            ),
            axis=1
        )

        null_count = df['ref_date'].isnull().sum()
        self.log(f"✅ ref_date 추출 완료: null {null_count}건")

        return df

    def _extract_naver_date_ref(
        self,
        title: str,
        published_at: str
    ) -> Optional[str]:
        """
        Naver 포스트에서 날짜를 추출합니다.

        Args:
            title: 포스트 제목
            published_at: 발행 시간

        Returns:
            YYYY-MM-DD 형식의 날짜 또는 None
        """
        # 1. title에서 추출
        if title:
            cleaned_title = clean_text(title)
            # 패턴: YYYYMMDD 또는 YYYY-MM-DD 등
            pattern_title = r'(\d{4})[^\d]?(\d{1,2})[^\d]?(\d{1,2})(?:[^\d]?[월화수목금토일])?'
            m_title = re.search(pattern_title, cleaned_title)
            if m_title:
                date_from_title = normalize_date(*m_title.groups())
                if date_from_title:
                    return date_from_title

        # 2. published_at에서 추출
        if published_at:
            cleaned_published_at = clean_text(published_at)
            # 패턴: YYYY. M. D.
            pattern_pub = r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.'
            m_pub = re.search(pattern_pub, cleaned_published_at)
            if m_pub:
                date_from_pub = normalize_date(*m_pub.groups())
                if date_from_pub:
                    return date_from_pub

        return None

    def _clean_body_text(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        body_text 필드에서 불필요한 헤더 제거.

        Naver 블로그는 "본문 기타 기능" 같은 헤더가 포함될 수 있음.
        이를 정규식으로 제거.
        """
        if 'body_text' in df.columns:
            df['body_text'] = df['body_text'].fillna('').str.replace(
                r'(?s)\A.*?본문\s*기타\s*기능\s*\n?',
                '',
                regex=True
            )
            self.log("✅ body_text 헤더 정리 완료")
        elif 'body' in df.columns:
            # 'body' 컬럼이 있는 경우 동일 처리
            df['body'] = df['body'].fillna('').str.replace(
                r'(?s)\A.*?본문\s*기타\s*기능\s*\n?',
                '',
                regex=True
            )
            self.log("✅ body 헤더 정리 완료")

        return df

    def _to_cleaned_documents(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        DataFrame을 CleanedNaverDocument dict 리스트로 변환합니다.
        """
        cleaned_docs = []

        for _, row in df.iterrows():
            # ref_date가 없는 경우 스킵 (또는 포함할지는 선택)
            if pd.isna(row.get('ref_date')):
                continue

            # 자연어 content 생성
            content = self._synthesize_naver_content(row)

            # Metadata 구성
            metadata = {
                "naver_blog_id": row.get('naver_blog_id', ''),
                "naver_log_no": row.get('naver_log_no', ''),
                "title": row.get('title', ''),
                "link": row.get('link', ''),
                "published_at": row.get('published_at', ''),
                "category": row.get('category', ''),
                "post_url": row.get('post_url', '')
            }

            # CleanedNaverDocument dict 생성
            cleaned_doc = {
                "original_id": str(row['id']),
                "content": content,
                "ref_date": row['ref_date'],
                "platform": "naver_blog",
                "doc_type": row.get('category', 'blog_post'),  # 카테고리를 doc_type으로 사용
                "author_id": str(row['author_id']),
                "author_full_name": row['author_full_name'],
                "is_valid": True,  # Naver 포스트는 기본적으로 유효
                "metadata": metadata
            }

            cleaned_docs.append(cleaned_doc)

        return cleaned_docs

    def _synthesize_naver_content(self, row: pd.Series) -> str:
        """
        Naver 블로그 포스트를 자연어 content로 변환합니다.

        구성:
        - 제목
        - 발행일 (자연어로)
        - 본문
        """
        title = row.get('title', '제목 없음')
        published_at = row.get('published_at', '')
        body = row.get('body', '')

        content_parts = []

        # 제목
        content_parts.append(f"제목: {title}")

        # 발행일
        if published_at:
            # "2024. 1. 15. 21:30" 같은 형식을 "2024년 1월 15일 발행"으로 변환
            try:
                # 날짜 부분만 추출
                date_match = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', published_at)
                if date_match:
                    year, month, day = date_match.groups()
                    published_str = f"{year}년 {int(month)}월 {int(day)}일 발행"
                    content_parts.append(f"발행일: {published_str}")
                else:
                    content_parts.append(f"발행일: {published_at}")
            except:
                content_parts.append(f"발행일: {published_at}")

        # 구분선
        content_parts.append("\n---\n")

        # 본문
        if body and body.strip():
            content_parts.append(body.strip())
        else:
            content_parts.append("(본문 없음)")

        return "\n".join(content_parts)
