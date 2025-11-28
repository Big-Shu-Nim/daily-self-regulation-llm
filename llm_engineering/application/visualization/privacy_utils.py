"""
Privacy utilities for public dashboard deployment.

공개 배포를 위한 개인정보 보호 유틸리티입니다.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


def filter_recent_days(df: pd.DataFrame, days: int = 7, ref_date: Optional[str] = None) -> pd.DataFrame:
    """
    최근 N일 데이터만 필터링합니다.

    Args:
        df: 원본 DataFrame
        days: 유지할 최근 일수 (기본: 7일)
        ref_date: 기준 날짜 (YYYY-MM-DD). None이면 오늘 날짜 사용

    Returns:
        필터링된 DataFrame
    """
    if df.empty:
        return df

    # 기준 날짜 설정
    if ref_date:
        reference_date = pd.to_datetime(ref_date)
    else:
        reference_date = pd.Timestamp.now()

    # N일 전 날짜 계산
    cutoff_date = reference_date - timedelta(days=days - 1)

    # 필터링
    df_filtered = df[df['start_datetime'] >= cutoff_date].copy()

    return df_filtered


def load_privacy_config(config_path: Optional[Path] = None) -> dict:
    """
    개인정보 필터링 설정 파일을 로드합니다.

    Args:
        config_path: 설정 파일 경로 (기본: 프로젝트 루트/privacy_filter_config.json)

    Returns:
        설정 딕셔너리
    """
    if config_path is None:
        project_root = Path(__file__).parents[3]
        config_path = project_root / "privacy_filter_config.json"

    if not config_path.exists():
        return {
            "masked_events": [],
            "masked_subcategories": []
        }

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  설정 파일 로드 실패: {e}")
        return {
            "masked_events": [],
            "masked_subcategories": []
        }


def create_sample_privacy_config(config_path: Optional[Path] = None):
    """
    샘플 개인정보 필터링 설정 파일을 생성합니다.

    Args:
        config_path: 설정 파일 경로 (기본: 프로젝트 루트/privacy_filter_config.json)
    """
    if config_path is None:
        project_root = Path(__file__).parents[3]
        config_path = project_root / "privacy_filter_config.json"

    sample_config = {
        "_comment": "개인정보 필터링 설정 파일 - 이 파일은 .gitignore에 포함되어 있습니다",
        "masked_events": [
            {
                "_comment": "이벤트명과 시간으로 특정 이벤트의 메모를 마스킹합니다",
                "event_name": "프로젝트 작업",
                "start_time": "22:15",
                "date": "2025-11-05"
            }
        ],
        "masked_subcategories": [
            "이직준비",
            "이사준비",
            "재무관리"
        ]
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_config, f, ensure_ascii=False, indent=2)

    print(f"✅ 샘플 설정 파일 생성됨: {config_path}")
    print(f"⚠️  이 파일은 .gitignore에 포함되어 있으므로 깃에 커밋되지 않습니다.")


def should_mask_event_by_config(row: pd.Series, config: dict) -> bool:
    """
    설정 파일 기반으로 해당 이벤트의 메모를 마스킹해야 하는지 판단합니다.

    Args:
        row: DataFrame의 행
        config: 설정 딕셔너리

    Returns:
        True if 마스킹 필요, False otherwise
    """
    # 1. 이벤트명 + 시간 기반 필터링
    event_name = str(row.get('event_name', ''))
    start_datetime = row.get('start_datetime')

    if pd.notna(start_datetime) and hasattr(start_datetime, 'strftime'):
        start_time = start_datetime.strftime('%H:%M')
        event_date = start_datetime.strftime('%Y-%m-%d')

        for masked_event in config.get('masked_events', []):
            if isinstance(masked_event, dict):
                # 이벤트명 매칭
                if masked_event.get('event_name') == event_name:
                    # 시간 매칭 (있으면)
                    if 'start_time' in masked_event:
                        if masked_event['start_time'] == start_time:
                            # 날짜 매칭 (있으면)
                            if 'date' in masked_event:
                                if masked_event['date'] == event_date:
                                    return True
                            else:
                                return True
                    else:
                        return True

    # 2. 서브카테고리 또는 이벤트명 기반 필터링 (일/생산 카테고리만 적용)
    category = row.get('category_name', '')
    sub_category = row.get('sub_category', '')

    masked_subcategories = config.get('masked_subcategories', [])

    if category == '일 / 생산':
        # 서브카테고리 체크
        if sub_category and sub_category in masked_subcategories:
            return True

        # 이벤트명 체크 - 정확히 일치하거나 특정 문자열로 시작하는 경우
        if event_name:
            for masked_keyword in masked_subcategories:
                # 정확히 일치
                if event_name == masked_keyword:
                    return True
                # 특정 키워드로 시작 (예: "이직준비_...")
                if event_name.startswith(masked_keyword + '_') or event_name.startswith(masked_keyword):
                    return True

    return False


def remove_duplicate_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    완전히 동일한 이벤트 중 하나를 제거합니다.

    동일 기준:
    - event_name, start_datetime, end_datetime, category_name, notes가 모두 동일

    Args:
        df: 원본 DataFrame

    Returns:
        중복 제거된 DataFrame
    """
    if df.empty:
        return df

    # 중복 체크할 컬럼들
    subset_cols = ['event_name', 'start_datetime', 'end_datetime', 'category_name', 'notes']

    # 존재하는 컬럼만 사용
    available_cols = [col for col in subset_cols if col in df.columns]

    if not available_cols:
        return df

    # 중복 제거 (첫 번째 발견된 것만 유지)
    df_dedup = df.drop_duplicates(subset=available_cols, keep='first').copy()

    removed_count = len(df) - len(df_dedup)
    if removed_count > 0:
        print(f"✅ 중복 이벤트 {removed_count}개 제거됨")

    return df_dedup


def mask_sensitive_notes(df: pd.DataFrame, config_path: Optional[Path] = None) -> pd.DataFrame:
    """
    카테고리별로 민감한 메모를 마스킹합니다.

    공개 정책:
    - ✅ 공개 가능: 일/생산, 학습/성장 카테고리의 notes
    - ⚠️ 부분 마스킹: 재충전, 일상관리, Drain - notes 제거
    - ❌ 완전 비공개: #인간관계 관련 상세 내용
    - 🔒 설정 파일 기반: 특정 이벤트 또는 서브카테고리 마스킹

    Args:
        df: 원본 DataFrame
        config_path: 개인정보 필터링 설정 파일 경로

    Returns:
        마스킹된 DataFrame (원본은 수정되지 않음)
    """
    df_masked = df.copy()

    # 설정 파일 로드
    config = load_privacy_config(config_path)

    # 공개 가능한 카테고리
    public_categories = ['일 / 생산', '학습 / 성장']

    # 1. 기본 메모 마스킹 (공개 불가 카테고리)
    mask_notes = ~df_masked['category_name'].isin(public_categories)
    df_masked.loc[mask_notes, 'notes'] = ''

    # 2. #인간관계 태그가 있는 경우 notes 추가 마스킹
    if 'has_relationship_tag' in df_masked.columns:
        relationship_mask = df_masked['has_relationship_tag'] == True
        df_masked.loc[relationship_mask, 'notes'] = ''

    # 3. 설정 파일 기반 특정 이벤트 마스킹
    for idx, row in df_masked.iterrows():
        if should_mask_event_by_config(row, config):
            df_masked.at[idx, 'notes'] = '개인정보, 마스킹처리됨'

    return df_masked


def anonymize_event_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    이벤트 이름에서 개인 식별 정보를 제거합니다.

    Args:
        df: 원본 DataFrame

    Returns:
        익명화된 DataFrame
    """
    df_anon = df.copy()

    # #인간관계 태그가 있는 이벤트는 "인간관계 활동"으로 일반화
    if 'has_relationship_tag' in df_anon.columns:
        relationship_mask = df_anon['has_relationship_tag'] == True
        df_anon.loc[relationship_mask, 'event_name'] = '인간관계 활동'

    return df_anon


def apply_public_privacy_filter(
    df: pd.DataFrame,
    days: int = 7,
    ref_date: Optional[str] = None,
    mask_notes: bool = True,
    anonymize_names: bool = True,
    remove_duplicates: bool = True,
    config_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    공개 배포를 위한 종합 프라이버시 필터를 적용합니다.

    Args:
        df: 원본 DataFrame
        days: 유지할 최근 일수
        ref_date: 기준 날짜 (YYYY-MM-DD)
        mask_notes: 민감한 메모 마스킹 여부
        anonymize_names: 이벤트 이름 익명화 여부
        remove_duplicates: 중복 이벤트 제거 여부
        config_path: 개인정보 필터링 설정 파일 경로

    Returns:
        프라이버시 필터가 적용된 DataFrame
    """
    # 0. 중복 제거 (가장 먼저 수행)
    if remove_duplicates:
        df_filtered = remove_duplicate_events(df)
    else:
        df_filtered = df.copy()

    # 1. 최근 N일 필터링
    df_filtered = filter_recent_days(df_filtered, days=days, ref_date=ref_date)

    # 2. 메모 마스킹
    if mask_notes:
        df_filtered = mask_sensitive_notes(df_filtered, config_path=config_path)

    # 3. 이벤트 이름 익명화
    if anonymize_names:
        df_filtered = anonymize_event_names(df_filtered)

    return df_filtered


def get_public_summary_stats(df: pd.DataFrame) -> dict:
    """
    공개 가능한 요약 통계를 반환합니다.

    Args:
        df: DataFrame (이미 필터링됨)

    Returns:
        공개 가능한 통계 딕셔너리
    """
    stats = {
        '총_활동_수': len(df),
        '총_기록_시간_분': df['duration_minutes'].sum() if not df.empty else 0,
        '데이터_기간_일수': (
            (df['start_datetime'].max() - df['start_datetime'].min()).days + 1
            if not df.empty else 0
        ),
        '카테고리별_활동_수': df['category_name'].value_counts().to_dict() if not df.empty else {},
    }

    # #인간관계 활동 수 (상세 내용은 제외)
    if 'has_relationship_tag' in df.columns:
        stats['인간관계_활동_수'] = df['has_relationship_tag'].sum()

    return stats


def validate_public_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    공개 데이터가 프라이버시 정책을 준수하는지 검증합니다.

    Args:
        df: 검증할 DataFrame

    Returns:
        (통과 여부, 경고 메시지 리스트)
    """
    warnings = []

    # 1. 날짜 범위 체크 (7일 이내인지)
    if not df.empty:
        date_range = (df['start_datetime'].max() - df['start_datetime'].min()).days + 1
        if date_range > 7:
            warnings.append(f"⚠️ 데이터 기간이 {date_range}일로 7일을 초과합니다.")

    # 2. 민감한 메모 체크
    sensitive_categories = ['재충전', '일상관리', 'Drain', '휴식 / 회복', '운동', '수면', 'Daily / Chore', '유지 / 정리']
    for category in sensitive_categories:
        cat_df = df[df['category_name'] == category]
        if not cat_df.empty and cat_df['notes'].notna().any() and (cat_df['notes'] != '').any():
            warnings.append(f"⚠️ '{category}' 카테고리에 메모가 남아있습니다.")

    # 3. #인간관계 상세 내용 체크
    if 'has_relationship_tag' in df.columns:
        relationship_events = df[df['has_relationship_tag'] == True]
        if not relationship_events.empty:
            if relationship_events['notes'].notna().any() and (relationship_events['notes'] != '').any():
                warnings.append("⚠️ #인간관계 활동에 메모가 남아있습니다.")

    passed = len(warnings) == 0
    return passed, warnings
