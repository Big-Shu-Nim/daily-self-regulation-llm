"""
Notion data preprocessor.

Notion 페이지를 전처리하고 문서 타입별로 분류합니다.
"""

import re
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd

from .base import BasePreprocessor
from .utils import (
    get_ancestor_chain,
    filter_by_ancestor_title,
    filter_by_parent_level_and_title,
    extract_date_from_text,
    extract_ref_date_from_title,
    extract_week_range_from_title,
    NOTION_DATE_PATTERNS,
    clean_text
)


class NotionPreprocessor(BasePreprocessor):
    """
    Notion 데이터를 전처리하는 클래스.

    핵심 작업:
    1. 무효 문서 마킹 (빈 내용, untitled, 템플릿만 있는 경우)
    2. Ancestor chain 생성
    3. 문서 타입별 분류:
       - daily_log_company: 회사 일일업무정리
       - diary: 습관 트래커 일기
       - weekly_report: 주간업무정리
       - general: 기타
    4. ref_date 추출 (title 또는 ancestor chain에서)
    5. 자연어 content 생성 (제목 + 경로 + 본문)
    """

    # 템플릿 패턴
    TEMPLATE_PATTERN = re.compile(
        r"^(?:###\s*(오늘의\s*특별한\s*점|오늘의\s*하이라이트|셀프\s*회고\s*:\s*칭찬|"
        r"셀프\s*회고\s*:\s*반성|내일\s*기대되는\s*첫작업)\s*-\s*\n*)+$",
        flags=re.MULTILINE
    )

    # 습관 트래커 전용 템플릿 패턴
    HABIT_TEMPLATE_PATTERN = re.compile(
        r"^(?:\s*"
        r"(?:###\s*(오늘의\s*특별한\s*점|오늘의\s*하이라이트|셀프\s*회고\s*:\s*칭찬|"
        r"셀프\s*회고\s*:\s*반성|내일\s*기대되는\s*첫작업)\s*-\s*)"
        r"[\n\s]*)+$",
        flags=re.MULTILINE
    )

    def clean(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Notion DataFrame을 전처리합니다.

        Args:
            df: 원본 Notion DataFrame

        Returns:
            CleanedNotionDocument에 맞는 dict 리스트
        """
        self.log("="*50)
        self.log(f"Notion 전처리 시작: {len(df)}건")

        # 1. 필수 컬럼 검증
        required_columns = [
            'id', 'title', 'content', 'ancestors', 'notion_page_id',
            'url', 'created_time', 'last_edited_time', 'author_id', 'author_full_name'
        ]
        self._validate_dataframe(df, required_columns)

        # 2. 무효 문서 마킹
        df = self._mark_invalid_documents(df)

        # 3. Ancestor chain 생성
        df["ancestor_chain"] = df["ancestors"].apply(get_ancestor_chain)
        self.log("✅ Ancestor chain 생성 완료")

        # 4. 문서 타입별 분류 및 처리
        df_company = self._process_company_daily_logs(df)
        df_diary = self._process_habit_tracker_diary(df)
        df_weekly = self._process_weekly_reports(df)

        # 5. 모든 분류 문서 통합
        df_all = pd.concat([df_company, df_diary, df_weekly], ignore_index=True)

        # 6. 원본과 병합
        df_merged = self._merge_with_original(df, df_all)

        # 6.5. General 타입의 ref_date 채우기 (created_time에서 추출)
        df_merged = self._fill_general_ref_dates(df_merged)

        # 6.6. MVP: General 타입 문서를 invalid로 마킹
        df_merged = self._mark_general_as_invalid(df_merged)

        # 7. Cleaned documents로 변환
        cleaned_documents = self._to_cleaned_documents(df_merged)

        self.log(f"✅ Notion 전처리 완료: {len(cleaned_documents)}건")
        self.log("="*50)

        return cleaned_documents

    def _mark_invalid_documents(self, df: pd.DataFrame) -> pd.DataFrame:
        """무효 문서를 마킹합니다."""
        def is_invalid(row):
            title = str(row.get("title", "") or "").strip().lower()
            content = str(row.get("content", "") or "").strip()

            # 제목이 없거나 untitled
            if title in ["", "untitled", "제목 없음", "no title", "없음"]:
                return True

            # 내용이 완전히 비었거나 공백만
            if not content or re.fullmatch(r"[\s\n\t]*", content):
                return True

            # 템플릿만 있는 경우
            if self.TEMPLATE_PATTERN.fullmatch(content):
                return True

            return False

        invalid_mask = df.apply(is_invalid, axis=1).astype(bool)
        df["is_valid"] = ~invalid_mask

        total = len(df)
        valid = int(df["is_valid"].sum())
        self.log(f"📊 총 문서 {total}개 중 유효 {valid}개 ({round(valid/total*100, 2)}%), 무효 {total-valid}개")

        return df

    def _process_company_daily_logs(self, df: pd.DataFrame) -> pd.DataFrame:
        """회사 일일업무정리 문서를 처리합니다."""
        df_company = filter_by_parent_level_and_title(df, '일일업무정리', min_sub_depth=1)

        if df_company.empty:
            self.log("⚠️ 회사 일일업무정리 문서 없음")
            return pd.DataFrame()

        # ref_date 추출
        df_company[["ref_date", "is_valid"]] = df_company.apply(
            lambda r: pd.Series(self._extract_ref_date(r["title"], r["ancestor_chain"])),
            axis=1
        )
        df_company["doc_type"] = "daily_log_company"

        valid_count = df_company['is_valid'].sum()
        null_count = df_company['ref_date'].isnull().sum()
        self.log(f"✅ 회사 일일업무정리: 총 {len(df_company)}개, 유효 {valid_count}개, ref_date null {null_count}개")

        return df_company

    def _process_habit_tracker_diary(self, df: pd.DataFrame) -> pd.DataFrame:
        """습관 트래커 일기 문서를 처리합니다."""
        df_diary = filter_by_ancestor_title(df, target_title='습관 리스트').copy()

        if df_diary.empty:
            self.log("⚠️ 습관 트래커 일기 문서 없음")
            return pd.DataFrame()

        # 유효성 검사 (템플릿만 있는 문서 제외)
        def is_valid_diary_text(text: str) -> bool:
            if not isinstance(text, str):
                return False
            stripped = text.strip()
            if stripped == "" or self.HABIT_TEMPLATE_PATTERN.match(stripped):
                return False
            return True

        df_diary["is_valid"] = df_diary["content"].apply(is_valid_diary_text)

        # created_time + 1일을 ref_date로 사용
        df_diary = self._add_day_and_format(df_diary, time_column="created_time")
        df_diary['doc_type'] = 'diary'

        valid_count = df_diary["is_valid"].sum()
        self.log(f"✅ 습관 트래커: 총 {len(df_diary)}개, 유효 {valid_count}개")

        return df_diary

    def _process_weekly_reports(self, df: pd.DataFrame) -> pd.DataFrame:
        """주간업무정리 문서를 처리합니다."""
        df_weekly = filter_by_ancestor_title(df, target_title='주간업무정리 ')

        if df_weekly.empty:
            self.log("⚠️ 주간업무정리 문서 없음")
            return pd.DataFrame()

        # ref_date 추출 (title에서 먼저 시도, 실패 시 ancestor chain에서 추출)
        df_weekly[["ref_date", "week_start_date", "week_end_date"]] = df_weekly.apply(
            lambda row: pd.Series(self._extract_weekly_dates(row)),
            axis=1
        )

        df_weekly["doc_type"] = "weekly_report"
        df_weekly["is_valid"] = True  # 주간보고서는 기본적으로 유효

        valid_count = df_weekly["is_valid"].sum()
        null_count = df_weekly["ref_date"].isnull().sum()
        self.log(f"✅ 주간업무정리: 총 {len(df_weekly)}개, 유효 {valid_count}개, ref_date null {null_count}개")

        return df_weekly

    def _extract_weekly_dates(self, row: pd.Series) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Weekly report의 날짜 정보를 추출합니다.

        Returns:
            (ref_date, week_start_date, week_end_date) 튜플
        """
        title = row.get("title", "")
        ancestor_chain = row.get("ancestor_chain", "")

        # 1. Title에서 먼저 시도
        week_start, week_end = extract_week_range_from_title(title)
        if week_start is not None and week_end is not None:
            ref_date = week_start.strftime('%Y-%m-%d')
            week_start_str = week_start.strftime('%Y-%m-%d')
            week_end_str = week_end.strftime('%Y-%m-%d')
            return (ref_date, week_start_str, week_end_str)

        # 2. Ancestor chain에서 시도 (부모 문서의 날짜 정보 상속)
        if ancestor_chain:
            # Ancestor chain을 분할하여 각 레벨에서 날짜 추출 시도
            nodes = [n.strip() for n in ancestor_chain.split('→') if n.strip()]
            # 역순으로 (자식 -> 부모) 탐색
            for node in reversed(nodes):
                week_start, week_end = extract_week_range_from_title(node)
                if week_start is not None and week_end is not None:
                    ref_date = week_start.strftime('%Y-%m-%d')
                    week_start_str = week_start.strftime('%Y-%m-%d')
                    week_end_str = week_end.strftime('%Y-%m-%d')
                    return (ref_date, week_start_str, week_end_str)

        # 3. 추출 실패
        return (None, None, None)

    def _extract_ref_date(
        self,
        title: str,
        ancestor_chain: Optional[str] = None
    ) -> Tuple[Optional[str], bool]:
        """
        Title 또는 ancestor chain에서 날짜를 추출합니다.

        Returns:
            (ref_date, is_valid) 튜플
        """
        def _extract_from_text(text: str) -> Optional[str]:
            pattern = r'(\d{4})[^\d]?(\d{1,2})[^\d]?(\d{1,2})(?:[^\d]?[월화수목금토일])?'
            m = re.search(pattern, text)
            if m:
                from .utils import normalize_date
                return normalize_date(*m.groups())
            return None

        # Title에서 먼저 시도
        if title:
            title_clean = clean_text(title)
            result = _extract_from_text(title_clean)
            if result:
                return result, True

        # Ancestor chain의 마지막 노드에서 시도
        if ancestor_chain:
            ancestor_clean = clean_text(ancestor_chain)
            nodes = [n.strip() for n in ancestor_clean.split('→') if n.strip()]
            if nodes:
                result = _extract_from_text(nodes[-1])
                if result:
                    return result, True

            # 전체 ancestor chain에서 시도
            result = _extract_from_text(ancestor_clean)
            if result:
                return result, True

        return None, False

    def _add_day_and_format(
        self,
        df: pd.DataFrame,
        time_column: str = 'created_time'
    ) -> pd.DataFrame:
        """특정 날짜/시간 컬럼에 하루를 더하고 ref_date 생성"""
        df_result = df.copy()
        df_result[time_column] = pd.to_datetime(df_result[time_column], errors='coerce')
        temp_date_col = '__temp_date_dt__'
        df_result[temp_date_col] = df_result[time_column] + pd.Timedelta('1 day')
        df_result['ref_date'] = df_result[temp_date_col].dt.strftime('%Y-%m-%d')
        df_result = df_result.drop(columns=[temp_date_col])
        return df_result

    def _merge_with_original(
        self,
        df_original: pd.DataFrame,
        df_classified: pd.DataFrame
    ) -> pd.DataFrame:
        """분류된 문서를 원본과 병합합니다."""
        # 병합할 컬럼 동적 결정 (week_start_date, week_end_date가 있으면 포함)
        merge_columns = ["id", "doc_type", "ref_date", "is_valid"]
        if "week_start_date" in df_classified.columns:
            merge_columns.append("week_start_date")
        if "week_end_date" in df_classified.columns:
            merge_columns.append("week_end_date")

        df_merged = df_original.merge(
            df_classified[merge_columns],
            on="id",
            how="left",
            suffixes=("", "_classified")
        )

        # 분류되지 않은 문서는 general로
        df_merged["doc_type"] = df_merged["doc_type"].fillna("general")
        df_merged["is_valid"] = df_merged["is_valid"].fillna(df_merged["is_valid_classified"])
        df_merged.drop(columns=["is_valid_classified"], inplace=True, errors='ignore')

        return df_merged

    def _fill_general_ref_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        General 타입 문서의 ref_date를 created_time에서 추출합니다.
        doc_type이 'general'이고 ref_date가 null인 경우에만 적용합니다.

        Args:
            df: 병합된 DataFrame

        Returns:
            ref_date가 채워진 DataFrame
        """
        # General 타입이면서 ref_date가 없는 문서 필터링
        general_mask = (df['doc_type'] == 'general') & (df['ref_date'].isnull())
        general_count = general_mask.sum()

        if general_count > 0:
            # created_time에서 날짜만 추출 (시간 부분 제거)
            df.loc[general_mask, 'ref_date'] = pd.to_datetime(
                df.loc[general_mask, 'created_time'],
                errors='coerce'
            ).dt.strftime('%Y-%m-%d')

            filled_count = df.loc[general_mask, 'ref_date'].notna().sum()
            self.log(f"✅ General 타입 ref_date 채우기: {filled_count}/{general_count}건")

        return df

    def _mark_general_as_invalid(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        MVP: General 타입 문서를 invalid로 마킹합니다.

        나중에 general 타입을 사용하려면 이 메서드를 제거하면 됩니다.

        Args:
            df: 병합된 DataFrame

        Returns:
            general 타입이 invalid로 마킹된 DataFrame
        """
        general_mask = df['doc_type'] == 'general'
        general_count = general_mask.sum()

        if general_count > 0:
            df.loc[general_mask, 'is_valid'] = False
            self.log(f"🚫 MVP: General 타입 {general_count}건을 invalid로 마킹")

        return df

    def _to_cleaned_documents(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        DataFrame을 CleanedNotionDocument dict 리스트로 변환합니다.
        """
        cleaned_docs = []

        for _, row in df.iterrows():
            # is_valid가 False인 경우 스킵 (또는 포함할지는 선택)
            if not row.get('is_valid', True):
                continue

            # 자연어 content 생성 (제목 + 경로 + 본문)
            content = self._synthesize_notion_content(row)

            # Metadata 구성
            metadata = {
                "notion_page_id": row.get('notion_page_id', ''),
                "title": row.get('title', ''),
                "url": row.get('url', ''),
                "ancestor_chain": row.get('ancestor_chain', ''),
                "created_time": row['created_time'].isoformat() if pd.notna(row.get('created_time')) else None,
                "last_edited_time": row['last_edited_time'].isoformat() if pd.notna(row.get('last_edited_time')) else None,
                "properties": row.get('properties', {}),
                "has_images": bool(row.get('image_gridfs_ids')),
                "image_gridfs_ids": row.get('image_gridfs_ids', []) or []
            }

            # Weekly report인 경우 주간 범위 정보 추가
            if row.get('doc_type') == 'weekly_report':
                if pd.notna(row.get('week_start_date')):
                    metadata['week_start_date'] = row['week_start_date']
                if pd.notna(row.get('week_end_date')):
                    metadata['week_end_date'] = row['week_end_date']

            # CleanedNotionDocument dict 생성
            cleaned_doc = {
                "original_id": str(row['id']),
                "content": content,
                "ref_date": row.get('ref_date') or '',
                "platform": "notion",
                "doc_type": row.get('doc_type', 'general'),
                "author_id": str(row['author_id']),
                "author_full_name": row['author_full_name'],
                "is_valid": bool(row.get('is_valid', True)),
                "metadata": metadata
            }

            cleaned_docs.append(cleaned_doc)

        return cleaned_docs

    def _synthesize_notion_content(self, row: pd.Series) -> str:
        """
        Notion 페이지를 자연어 content로 변환합니다.

        구성:
        - 제목
        - 경로 (ancestor chain)
        - 본문 (마크다운)
        """
        title = row.get('title', '제목 없음')
        ancestor_chain = row.get('ancestor_chain', '')
        body = row.get('content', '')

        content_parts = []

        # 제목
        content_parts.append(f"제목: {title}")

        # 경로
        if ancestor_chain:
            content_parts.append(f"경로: {ancestor_chain}")

        # 구분선
        content_parts.append("\n---\n")

        # 본문
        if body and body.strip():
            content_parts.append(body.strip())
        else:
            content_parts.append("(내용 없음)")

        return "\n".join(content_parts)
