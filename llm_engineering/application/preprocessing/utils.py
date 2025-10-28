"""
Common utility functions for preprocessing.

텍스트 정리, 날짜 추출, DataFrame 조작 등 모든 preprocessor에서 사용하는 공통 함수들.
"""

import json
import re
from ast import literal_eval
from typing import Optional, Any

import numpy as np
import pandas as pd


# ===== 텍스트 처리 유틸리티 =====

def clean_text(text: str) -> str:
    """
    제어문자, 공백, 괄호 등을 제거하여 텍스트를 정리합니다.

    Args:
        text: 정리할 텍스트

    Returns:
        정리된 텍스트
    """
    text = re.sub(r'[\n\t\r]+', ' ', str(text))
    text = re.sub(r'\([^)]*\)', '', text)  # 괄호 내용 제거
    text = text.replace('→', '→')
    return text.strip()


def is_valid_text(text: str, min_length: int = 20) -> bool:
    """
    텍스트가 유효한지 검사합니다.

    Args:
        text: 검사할 텍스트
        min_length: 최소 길이

    Returns:
        유효하면 True
    """
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped or len(stripped) < min_length:
        return False
    return True


def is_template_content(content: str, template_pattern: re.Pattern) -> bool:
    """
    내용이 템플릿만 있는지 검사합니다.

    Args:
        content: 검사할 내용
        template_pattern: 템플릿 정규식 패턴

    Returns:
        템플릿만 있으면 True
    """
    if not isinstance(content, str):
        return False
    stripped = content.strip()
    if not stripped:
        return True
    return bool(template_pattern.match(stripped))


# ===== 날짜 처리 유틸리티 =====

def normalize_date(year: Any, month: Any, day: Any) -> Optional[str]:
    """
    년/월/일을 YYYY-MM-DD 형식으로 정규화합니다.

    Args:
        year: 년
        month: 월
        day: 일

    Returns:
        YYYY-MM-DD 형식의 날짜 문자열 또는 None
    """
    try:
        return pd.to_datetime(
            f"{int(year)}-{int(month):02d}-{int(day):02d}",
            errors='raise'
        ).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None


def extract_date_from_text(text: str, patterns: list[tuple]) -> Optional[str]:
    """
    텍스트에서 여러 패턴을 사용하여 날짜를 추출합니다.

    Args:
        text: 날짜를 추출할 텍스트
        patterns: (regex_pattern, year_group, month_group, day_group) 튜플 리스트

    Returns:
        YYYY-MM-DD 형식의 날짜 또는 None

    예시:
        patterns = [
            (r'(\\d{4})년\\s*(\\d{1,2})월\\s*(\\d{1,2})일', 1, 2, 3),
            (r'(\\d{4})-(\\d{1,2})-(\\d{1,2})', 1, 2, 3),
        ]
    """
    if not isinstance(text, str):
        return None

    text_clean = clean_text(text)

    for pattern, year_idx, month_idx, day_idx in patterns:
        match = re.search(pattern, text_clean)
        if match:
            try:
                year = int(match.group(year_idx)) if year_idx else None
                month = int(match.group(month_idx)) if month_idx else None
                day = int(match.group(day_idx)) if day_idx else None

                # Handle 2-digit year
                if year and year < 100:
                    year = 2000 + year if year < 50 else 1900 + year

                if year and month and day:
                    return normalize_date(year, month, day)
            except (ValueError, IndexError):
                continue

    return None


# 공통 날짜 패턴
NOTION_DATE_PATTERNS = [
    (r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', 1, 2, 3),  # 2024년 1월 15일
    (r'(\d{4})-(\d{1,2})-(\d{1,2})', 1, 2, 3),            # 2024-01-15
    (r'(\d{2})\.(\d{1,2})\.(\d{1,2})', 1, 2, 3),         # 24.01.15
    (r'(\d{1,2})월\s*(\d{1,2})일', None, 1, 2),           # 1월 15일
]

NAVER_DATE_PATTERNS = [
    (r'(\d{4})(\d{2})(\d{2})', 1, 2, 3),  # 20240115
    (r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', 1, 2, 3),
    (r'(\d{4})-(\d{1,2})-(\d{1,2})', 1, 2, 3),
]


def extract_ref_date_from_title(title: str) -> Optional[pd.Timestamp]:
    """
    다양한 형식의 제목에서 기준 날짜(ref_date)를 추출합니다.
    패턴 매칭은 구체적인 순서부터 진행합니다.

    주차 패턴의 경우 주의 시작일을 반환합니다 (월요일 기준이 아닌 해당 월의 N주차 시작일).

    Args:
        title: 날짜를 추출할 제목

    Returns:
        추출된 날짜 (pd.Timestamp) 또는 None (pd.NaT)

    Examples:
        >>> extract_ref_date_from_title('2023_0828-0901')
        Timestamp('2023-08-28 00:00:00')

        >>> extract_ref_date_from_title('2024년 3월 3주차')
        Timestamp('2024-03-15 00:00:00')  # 3주차 시작일 (15일)

        >>> extract_ref_date_from_title('2025_ 7월 2주차')
        Timestamp('2025-07-08 00:00:00')  # 2주차 시작일 (8일)
    """
    if not isinstance(title, str):
        return pd.NaT

    # 패턴 1: 'YYYY_MMDD-MMDD' 형식 (예: '2023_0828-0901')
    match = re.search(r'(\d{4})_(\d{2})(\d{2})', title)
    if match:
        year, month, day = match.groups()
        try:
            return pd.to_datetime(f'{year}-{month}-{day}')
        except ValueError:
            pass  # 잘못된 날짜 형식일 경우 다음 패턴으로 넘어감

    # 패턴 2: 'YYYY년 M월 W주차' 형식 (예: '2024년 3월 3주차')
    match = re.search(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*주차', title)
    if match:
        year, month, week = map(int, match.groups())
        # N주차의 시작일을 (N-1)*7 + 1일로 계산
        day = max(1, (week - 1) * 7 + 1)
        try:
            return pd.to_datetime(f'{year}-{month}-{day}')
        except ValueError:
            pass

    # 패턴 3: 'YYYY_ M월 W주차' 형식 (예: '2025_ 7월 2주차')
    match = re.search(r'(\d{4})_\s*(\d{1,2})\s*월\s*(\d{1,2})\s*주차', title)
    if match:
        year, month, week = map(int, match.groups())
        day = max(1, (week - 1) * 7 + 1)
        try:
            return pd.to_datetime(f'{year}-{month}-{day}')
        except ValueError:
            pass

    # 모든 패턴에 해당하지 않으면 NaT (Not a Time) 반환
    return pd.NaT


def extract_week_range_from_title(title: str) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """
    제목에서 주간 범위(week_start, week_end)를 추출합니다.

    주차 패턴인 경우 주의 시작일과 종료일(+6일)을 반환합니다.
    날짜 범위 패턴(YYYY_MMDD-MMDD)인 경우 시작일과 종료일을 반환합니다.

    Args:
        title: 날짜 범위를 추출할 제목

    Returns:
        (week_start, week_end) 튜플. 추출 실패 시 (None, None)

    Examples:
        >>> extract_week_range_from_title('2024년 3월 3주차')
        (Timestamp('2024-03-15'), Timestamp('2024-03-21'))

        >>> extract_week_range_from_title('2023_0828-0901')
        (Timestamp('2023-08-28'), Timestamp('2023-09-01'))
    """
    if not isinstance(title, str):
        return (None, None)

    # 패턴 1: 'YYYY_MMDD-MMDD' 형식 (명시적 범위)
    match = re.search(r'(\d{4})_(\d{2})(\d{2})-(\d{2})(\d{2})', title)
    if match:
        year, start_month, start_day, end_month, end_day = match.groups()
        try:
            week_start = pd.to_datetime(f'{year}-{start_month}-{start_day}')
            week_end = pd.to_datetime(f'{year}-{end_month}-{end_day}')
            return (week_start, week_end)
        except ValueError:
            pass

    # 패턴 2: 'YYYY년 M월 W주차' 형식
    match = re.search(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*주차', title)
    if match:
        year, month, week = map(int, match.groups())
        day = max(1, (week - 1) * 7 + 1)
        try:
            week_start = pd.to_datetime(f'{year}-{month}-{day}')
            week_end = week_start + pd.Timedelta(days=6)
            return (week_start, week_end)
        except ValueError:
            pass

    # 패턴 3: 'YYYY_ M월 W주차' 형식
    match = re.search(r'(\d{4})_\s*(\d{1,2})\s*월\s*(\d{1,2})\s*주차', title)
    if match:
        year, month, week = map(int, match.groups())
        day = max(1, (week - 1) * 7 + 1)
        try:
            week_start = pd.to_datetime(f'{year}-{month}-{day}')
            week_end = week_start + pd.Timedelta(days=6)
            return (week_start, week_end)
        except ValueError:
            pass

    return (None, None)


# ===== DataFrame 처리 유틸리티 =====

def parse_content_field(value: Any) -> dict:
    """
    content 필드를 안전하게 파싱합니다.

    Args:
        value: 파싱할 값 (dict, str, None 등)

    Returns:
        파싱된 딕셔너리
    """
    if isinstance(value, dict):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return {}
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {}
        try:
            return json.loads(s)
        except Exception:
            try:
                return literal_eval(s)
            except Exception:
                return {}
    return {}


def flatten_dict_column(
    df: pd.DataFrame,
    target_column: str,
    drop_original: bool = True
) -> pd.DataFrame:
    """
    DataFrame의 딕셔너리 컬럼을 개별 컬럼으로 평탄화합니다.

    Args:
        df: DataFrame
        target_column: 평탄화할 컬럼명
        drop_original: 원본 컬럼 삭제 여부

    Returns:
        평탄화된 DataFrame
    """
    df_copy = df.copy()
    flattened_data = df_copy[target_column].apply(
        lambda x: pd.Series(x) if isinstance(x, dict) else pd.Series({})
    )
    if drop_original:
        df_copy = df_copy.drop(columns=[target_column])
    return pd.concat([df_copy, flattened_data], axis=1)


def safe_parse_json_column(df: pd.DataFrame, column: str) -> pd.Series:
    """
    JSON/dict 컬럼을 안전하게 파싱합니다.

    Args:
        df: DataFrame
        column: 파싱할 컬럼명

    Returns:
        파싱된 Series
    """
    def parse_value(val):
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return {}
        return {}

    return df[column].map(parse_value)


# ===== Notion 특화 유틸리티 =====

def get_ancestor_chain(ancestors: list) -> str:
    """
    Notion ancestors 리스트에서 체인 문자열을 생성합니다.
    'Workspace Root'는 제외합니다.

    Args:
        ancestors: Notion ancestor 리스트

    Returns:
        " → "로 연결된 ancestor 체인
    """
    titles = [
        a["title"].strip()
        for a in ancestors
        if a.get("title") and "Workspace Root" not in a["title"]
    ]
    return " → ".join(titles)


def filter_by_ancestor_title(
    df: pd.DataFrame,
    target_title: str,
    ancestor_column: str = 'ancestors'
) -> pd.DataFrame:
    """
    특정 title을 가진 조상을 포함하는 행만 필터링합니다.

    Args:
        df: DataFrame
        target_title: 찾을 ancestor title
        ancestor_column: ancestors 컬럼명

    Returns:
        필터링된 DataFrame
    """
    def safe_parse_and_check(ancestors_data):
        if ancestors_data is None or not ancestors_data:
            return False

        ancestors_list = []
        if isinstance(ancestors_data, str) and ancestors_data.strip().startswith('['):
            try:
                ancestors_list = json.loads(ancestors_data.replace("'", '"'))
            except json.JSONDecodeError:
                return False
        elif isinstance(ancestors_data, list):
            ancestors_list = ancestors_data
        else:
            return False

        for ancestor in ancestors_list:
            if isinstance(ancestor, dict) and ancestor.get('title') == target_title:
                return True
        return False

    filter_mask = df[ancestor_column].apply(safe_parse_and_check)
    return df[filter_mask].copy()


def filter_by_parent_level_and_title(
    df: pd.DataFrame,
    target_parent_title: str,
    min_sub_depth: int = 2,
    ancestor_column: str = 'ancestors'
) -> pd.DataFrame:
    """
    특정 부모 title 아래에 있으며 중간 레이어 깊이가 특정 값 이상인 문서만 필터링합니다.

    Args:
        df: DataFrame
        target_parent_title: 찾을 부모 title
        min_sub_depth: 최소 하위 깊이
        ancestor_column: ancestors 컬럼명

    Returns:
        필터링된 DataFrame
    """
    def check_ancestor_structure(ancestors_data):
        if ancestors_data is None or not ancestors_data:
            return False

        ancestors_list = []
        if isinstance(ancestors_data, str):
            try:
                ancestors_list = json.loads(ancestors_data.replace("'", '"'))
            except json.JSONDecodeError:
                return False
        elif isinstance(ancestors_data, list):
            ancestors_list = ancestors_data
        else:
            return False

        ancestors_list = [
            a for a in ancestors_list
            if a.get("title") and "Workspace Root" not in a["title"]
        ]
        titles = [a.get("title").strip() for a in ancestors_list]

        if target_parent_title not in titles:
            return False

        parent_index = titles.index(target_parent_title)
        sub_depth = len(titles) - (parent_index + 1)
        return sub_depth >= min_sub_depth

    mask = df[ancestor_column].apply(check_ancestor_structure)
    return df[mask].copy()
