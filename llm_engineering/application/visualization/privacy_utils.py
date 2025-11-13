"""
Privacy utilities for public dashboard deployment.

공개 배포를 위한 개인정보 보호 유틸리티입니다.
"""

import pandas as pd
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


def mask_sensitive_notes(df: pd.DataFrame) -> pd.DataFrame:
    """
    카테고리별로 민감한 메모를 마스킹합니다.

    공개 정책:
    - ✅ 공개 가능: 일/생산, 학습/성장 카테고리의 notes
    - ⚠️ 부분 마스킹: 재충전, 일상관리, Drain - notes 제거
    - ❌ 완전 비공개: #인간관계 관련 상세 내용

    Args:
        df: 원본 DataFrame

    Returns:
        마스킹된 DataFrame (원본은 수정되지 않음)
    """
    df_masked = df.copy()

    # 공개 가능한 카테고리
    public_categories = ['일 / 생산', '학습 / 성장']

    # 메모 마스킹
    mask_notes = ~df_masked['category_name'].isin(public_categories)
    df_masked.loc[mask_notes, 'notes'] = ''

    # #인간관계 태그가 있는 경우 notes 추가 마스킹
    if 'has_relationship_tag' in df_masked.columns:
        relationship_mask = df_masked['has_relationship_tag'] == True
        df_masked.loc[relationship_mask, 'notes'] = ''

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
    anonymize_names: bool = True
) -> pd.DataFrame:
    """
    공개 배포를 위한 종합 프라이버시 필터를 적용합니다.

    Args:
        df: 원본 DataFrame
        days: 유지할 최근 일수
        ref_date: 기준 날짜 (YYYY-MM-DD)
        mask_notes: 민감한 메모 마스킹 여부
        anonymize_names: 이벤트 이름 익명화 여부

    Returns:
        프라이버시 필터가 적용된 DataFrame
    """
    # 1. 최근 N일 필터링
    df_filtered = filter_recent_days(df, days=days, ref_date=ref_date)

    # 2. 메모 마스킹
    if mask_notes:
        df_filtered = mask_sensitive_notes(df_filtered)

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
