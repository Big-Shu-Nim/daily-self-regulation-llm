"""
Weekly Metrics Calculator.

주간 데이터에서 사전 계산된 메트릭을 추출합니다.
V2 프롬프트에서 LLM이 직접 계산하지 않도록 합니다.
"""

import pandas as pd


# Agency 모드 매핑
AGENCY_MODE_MAPPING = {
    "creator": ["일 / 생산",],  # 운동도 목표 지향적이면 creator
    "learner": ["학습 / 성장"],
    "maintainer": ["유지 / 정리", "daily/chore"],
    "recharger": ["수면", "휴식/회복","운동"],
    "Drain": ["Drain"],  # 감정관리는 맥락에 따라 다를 수 있음
}

# 역 매핑 (카테고리 → 모드)
CATEGORY_TO_MODE = {}
for mode, categories in AGENCY_MODE_MAPPING.items():
    for cat in categories:
        CATEGORY_TO_MODE[cat] = mode


def compute_weekly_metrics(df: pd.DataFrame, start_date: str, end_date: str) -> dict:
    """
    DataFrame에서 주간 메트릭을 계산합니다.

    Args:
        df: 주간 캘린더 데이터 DataFrame
        start_date: 주 시작 날짜
        end_date: 주 종료 날짜

    Returns:
        사전 계산된 메트릭 딕셔너리
    """
    if df is None or df.empty:
        return _empty_metrics(start_date, end_date)

    metrics = {
        "range": {"start": start_date, "end": end_date},
        "summary": {},
        "hours": {
            "categories": {},
            "modes": {},
        },
        "sleep": {},
        "drain": {},
        "daily_breakdown": {},
    }

    # 1. 기본 통계
    total_minutes = df["duration_minutes"].sum()
    total_hours = total_minutes / 60
    metrics["summary"] = {
        "total_hours": round(total_hours, 1),
        "total_activities": len(df),
        "unique_dates": df["ref_date"].nunique() if "ref_date" in df.columns else 0,
    }

    # 2. 카테고리별 시간
    category_hours = _compute_category_hours(df)
    metrics["hours"]["categories"] = category_hours

    # 3. Agency 모드별 시간
    mode_hours = _compute_mode_hours(category_hours)
    metrics["hours"]["modes"] = mode_hours

    # 4. 수면 통계
    metrics["sleep"] = _compute_sleep_stats(df)

    # 5. Drain 지표
    metrics["drain"] = _compute_drain_stats(df, total_minutes)

    # 6. 일별 분석
    metrics["daily_breakdown"] = _compute_daily_breakdown(df)

    # 7. 태그 통계
    metrics["tags"] = _compute_tag_stats(df)

    # 8. 회복 비율 (Recharger / Drain)
    recharge_minutes = (
        category_hours.get("수면", 0) + category_hours.get("휴식/회복", 0)
    ) * 60
    drain_minutes = category_hours.get("Drain", 0) * 60
    if drain_minutes > 0:
        metrics["recovery_ratio"] = round(recharge_minutes / drain_minutes, 2)
    else:
        # Drain이 0이면 이상적인 상태 - null로 표시
        metrics["recovery_ratio"] = None
        metrics["recovery_ratio_note"] = "Drain 없음 (이상적)"

    return metrics


def _compute_category_hours(df: pd.DataFrame) -> dict:
    """카테고리별 시간 계산"""
    category_col = "category_name" if "category_name" in df.columns else "calendar_name"

    if category_col not in df.columns:
        return {}

    category_minutes = df.groupby(category_col)["duration_minutes"].sum()
    return {cat: round(mins / 60, 1) for cat, mins in category_minutes.items()}


def _compute_mode_hours(category_hours: dict) -> dict:
    """Agency 모드별 시간 계산"""
    mode_hours = {mode: 0.0 for mode in AGENCY_MODE_MAPPING.keys()}

    for category, hours in category_hours.items():
        mode = CATEGORY_TO_MODE.get(category)
        if mode:
            mode_hours[mode] += hours
        elif "인간관계" in category:
            # 인간관계는 recharger로 분류
            mode_hours["recharger"] += hours
        else:
            # 기타는 maintainer로 분류
            mode_hours["maintainer"] += hours

    return {mode: round(hours, 1) for mode, hours in mode_hours.items()}


def _compute_sleep_stats(df: pd.DataFrame) -> dict:
    """수면 통계 계산"""
    category_col = "category_name" if "category_name" in df.columns else "calendar_name"

    sleep_df = df[df[category_col] == "수면"] if category_col in df.columns else pd.DataFrame()

    if sleep_df.empty:
        return {
            "avg_h": 0.0,
            "min_h": 0.0,
            "max_h": 0.0,
            "total_h": 0.0,
            "wake_variability_note": "수면 데이터 없음",
        }

    # 날짜별 수면 시간 집계
    if "ref_date" in sleep_df.columns:
        daily_sleep = sleep_df.groupby("ref_date")["duration_minutes"].sum() / 60
        avg_sleep = daily_sleep.mean()
        min_sleep = daily_sleep.min()
        max_sleep = daily_sleep.max()
        std_sleep = daily_sleep.std() if len(daily_sleep) > 1 else 0

        # 기상 시간 분석 (end_datetime 기준)
        wake_note = ""
        if "end_datetime" in sleep_df.columns:
            try:
                wake_times = pd.to_datetime(sleep_df["end_datetime"]).dt.hour
                if len(wake_times) > 0:
                    avg_wake = wake_times.mean()
                    wake_note = f"평균 기상 ~{int(avg_wake)}시"
                    if std_sleep > 1.5:
                        wake_note += " (불규칙)"
            except Exception:
                pass

        return {
            "avg_h": round(avg_sleep, 1),
            "min_h": round(min_sleep, 1),
            "max_h": round(max_sleep, 1),
            "total_h": round(daily_sleep.sum(), 1),
            "days_tracked": len(daily_sleep),
            "wake_variability_note": wake_note or f"표준편차 {round(std_sleep, 1)}h",
        }

    # ref_date가 없는 경우
    total_sleep = sleep_df["duration_minutes"].sum() / 60
    return {
        "avg_h": round(total_sleep / 7, 1),  # 7일로 나눔
        "min_h": 0.0,
        "max_h": 0.0,
        "total_h": round(total_sleep, 1),
        "wake_variability_note": "일별 데이터 부족",
    }


def _compute_drain_stats(df: pd.DataFrame, total_minutes: float) -> dict:
    """Drain 통계 계산"""
    category_col = "category_name" if "category_name" in df.columns else "calendar_name"

    # Drain 필터 (카테고리명 "Drain" 또는 is_risky_recharger 플래그)
    drain_keywords = ["Drain", "충동루프", "유튜브", "넷플릭스", "SNS"]
    if category_col in df.columns:
        drain_df = df[
            df[category_col].str.contains("|".join(drain_keywords), case=False, na=False)
            | df.get("is_risky_recharger", pd.Series([False] * len(df)))
        ]
    else:
        drain_df = df[df.get("is_risky_recharger", pd.Series([False] * len(df)))]

    drain_minutes = drain_df["duration_minutes"].sum() if not drain_df.empty else 0

    # 수면 제외한 깨어있는 시간
    sleep_minutes = 0
    if category_col in df.columns:
        sleep_df = df[df[category_col] == "수면"]
        sleep_minutes = sleep_df["duration_minutes"].sum()

    awake_minutes = total_minutes - sleep_minutes
    drain_percent = (drain_minutes / awake_minutes * 100) if awake_minutes > 0 else 0

    # 심야 Drain (23:00~03:00)
    late_night_minutes = 0
    if "start_datetime" in df.columns and not drain_df.empty:
        try:
            drain_df = drain_df.copy()
            drain_df["hour"] = pd.to_datetime(drain_df["start_datetime"]).dt.hour
            late_night_mask = (drain_df["hour"] >= 23) | (drain_df["hour"] < 3)
            late_night_minutes = drain_df.loc[late_night_mask, "duration_minutes"].sum()
        except Exception:
            pass

    # 알코올 감지
    alcohol_keywords = ["맥주", "소주", "와인", "하이볼", "혼술", "음주", "술"]
    alcohol_count = 0
    alcohol_minutes = 0
    if "notes" in df.columns:
        alcohol_mask = df["notes"].str.contains("|".join(alcohol_keywords), case=False, na=False)
        alcohol_df = df[alcohol_mask]
        alcohol_count = len(alcohol_df)
        alcohol_minutes = alcohol_df["duration_minutes"].sum()
    if "event_name" in df.columns:
        alcohol_event_mask = df["event_name"].str.contains("|".join(alcohol_keywords), case=False, na=False)
        alcohol_event_df = df[alcohol_event_mask & ~df.index.isin(df[alcohol_mask].index if "notes" in df.columns else [])]
        alcohol_count += len(alcohol_event_df)
        alcohol_minutes += alcohol_event_df["duration_minutes"].sum()

    return {
        "total_minutes": int(drain_minutes),
        "total_hours": round(drain_minutes / 60, 1),
        "drain_percent": round(drain_percent, 1),
        "late_night_minutes_23_03": int(late_night_minutes),
        "alcohol_sessions": alcohol_count,
        "alcohol_minutes_total": int(alcohol_minutes),
        "risky_recharger_count": int(df.get("is_risky_recharger", pd.Series([False] * len(df))).sum()),
    }


def _compute_daily_breakdown(df: pd.DataFrame) -> dict:
    """일별 분석"""
    if "ref_date" not in df.columns:
        return {}

    daily_stats = {}
    for date, group in df.groupby("ref_date"):
        total_mins = group["duration_minutes"].sum()
        daily_stats[date] = {
            "total_hours": round(total_mins / 60, 1),
            "activity_count": len(group),
            "relationship_count": int(group.get("has_relationship_tag", pd.Series([False] * len(group))).sum()),
            "risky_count": int(group.get("is_risky_recharger", pd.Series([False] * len(group))).sum()),
        }

    return daily_stats


def _compute_tag_stats(df: pd.DataFrame) -> dict:
    """태그 통계 계산"""
    stats = {
        "relationship_total": 0,
        "risky_recharger_total": 0,
        "emotion_event_total": 0,
    }

    if "has_relationship_tag" in df.columns:
        stats["relationship_total"] = int(df["has_relationship_tag"].sum())
    if "is_risky_recharger" in df.columns:
        stats["risky_recharger_total"] = int(df["is_risky_recharger"].sum())
    if "has_emotion_event" in df.columns:
        stats["emotion_event_total"] = int(df["has_emotion_event"].sum())

    return stats


def _empty_metrics(start_date: str, end_date: str) -> dict:
    """빈 메트릭 반환"""
    return {
        "range": {"start": start_date, "end": end_date},
        "summary": {
            "total_hours": 0.0,
            "total_activities": 0,
            "unique_dates": 0,
        },
        "hours": {
            "categories": {},
            "modes": {
                "creator": 0.0,
                "learner": 0.0,
                "maintainer": 0.0,
                "recharger": 0.0,
                "Drain": 0.0,
            },
        },
        "sleep": {
            "avg_h": 0.0,
            "min_h": 0.0,
            "max_h": 0.0,
            "total_h": 0.0,
            "wake_variability_note": "데이터 없음",
        },
        "drain": {
            "total_minutes": 0,
            "total_hours": 0.0,
            "drain_percent": 0.0,
            "late_night_minutes_23_03": 0,
            "alcohol_sessions": 0,
            "alcohol_minutes_total": 0,
            "risky_recharger_count": 0,
        },
        "daily_breakdown": {},
        "tags": {
            "relationship_total": 0,
            "risky_recharger_total": 0,
            "emotion_event_total": 0,
        },
        "recovery_ratio": None,
        "recovery_ratio_note": "데이터 없음",
    }


__all__ = ["compute_weekly_metrics", "AGENCY_MODE_MAPPING", "CATEGORY_TO_MODE"]
