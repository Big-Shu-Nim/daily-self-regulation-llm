"""
활동 리포트 - 실험용 대시보드

실험 기능:
- 일별/주간 리포트 타입 선택
- 다양한 LLM 모델 선택 및 비교
- 프라이버시 필터 on/off 토글
- 모델별 성능 메트릭 (토큰, 시간, 비용)
- 전체 데이터 접근 가능

왼쪽: Interactive 시각화 인사이트
오른쪽: 실험용 LLM 피드백
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

from llm_engineering.domain.cleaned_documents import CleanedCalendarDocument
from llm_engineering.application.feedback.daily.generator import DailyFeedbackGenerator
from llm_engineering.application.feedback.weekly.generator import WeeklyFeedbackGenerator
from llm_engineering.application.feedback.monthly.generator import MonthlyFeedbackGenerator
from llm_engineering.application.visualization.daily_report_interactive import (
    format_duration,
    plot_agency_pie_chart_interactive,
    plot_category_distribution_interactive,
    plot_sleep_breakdown_interactive,
    plot_work_by_event_interactive,
    plot_learning_by_event_interactive,
    plot_recharge_by_event_interactive,
    plot_drain_by_event_interactive,
    plot_maintenance_by_event_interactive,
    plot_relationship_by_agency_interactive,
)
from llm_engineering.application.visualization.privacy_utils import (
    apply_public_privacy_filter,
)


# Tooltip 스타일 정의
TOOLTIP_CSS = """
<style>
.chart-title-tooltip {
    position: relative;
    display: inline-block;
    cursor: help;
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.chart-title-tooltip .tooltiptext {
    visibility: hidden;
    width: 300px;
    background-color: #262730;
    color: #fafafa;
    text-align: left;
    padding: 10px;
    border-radius: 6px;
    border: 1px solid #464646;

    position: absolute;
    z-index: 1000;
    bottom: 125%;
    left: 50%;
    margin-left: -150px;

    opacity: 0;
    transition: opacity 0.3s;

    font-size: 0.875rem;
    font-weight: normal;
}

.chart-title-tooltip:hover .tooltiptext {
    visibility: visible;
    opacity: 1;
}

.chart-title-tooltip .tooltiptext::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: #464646 transparent transparent transparent;
}
</style>
"""


# 사용 가능한 모델 목록
OPENAI_MODELS = {
    # GPT-5 Series (최신)
    "gpt-5.1": {"name": "GPT-5.1 (최신)", "cost_per_1k_input": 10.0, "cost_per_1k_output": 30.0},
    "gpt-5": {"name": "GPT-5", "cost_per_1k_input": 8.0, "cost_per_1k_output": 24.0},
    "gpt-5-pro": {"name": "GPT-5 Pro", "cost_per_1k_input": 12.0, "cost_per_1k_output": 36.0},
    "gpt-5-mini": {"name": "GPT-5 Mini", "cost_per_1k_input": 1.0, "cost_per_1k_output": 3.0},
    "gpt-5-nano": {"name": "GPT-5 Nano", "cost_per_1k_input": 0.5, "cost_per_1k_output": 1.5},

    # GPT-4.1 Series
    "gpt-4.1": {"name": "GPT-4.1", "cost_per_1k_input": 7.0, "cost_per_1k_output": 21.0},
    "gpt-4.1-mini": {"name": "GPT-4.1 Mini", "cost_per_1k_input": 0.8, "cost_per_1k_output": 2.4},
    "gpt-4.1-nano": {"name": "GPT-4.1 Nano", "cost_per_1k_input": 0.4, "cost_per_1k_output": 1.2},

    # GPT-4o Series
    "gpt-4o": {"name": "GPT-4o", "cost_per_1k_input": 5.0, "cost_per_1k_output": 15.0},
    "gpt-4o-mini": {"name": "GPT-4o Mini", "cost_per_1k_input": 0.15, "cost_per_1k_output": 0.60},

    # GPT-4 Series
    "gpt-4-turbo": {"name": "GPT-4 Turbo", "cost_per_1k_input": 10.0, "cost_per_1k_output": 30.0},
    "gpt-4": {"name": "GPT-4", "cost_per_1k_input": 30.0, "cost_per_1k_output": 60.0},

    # GPT-3.5 Series
    "gpt-3.5-turbo": {"name": "GPT-3.5 Turbo", "cost_per_1k_input": 0.50, "cost_per_1k_output": 1.50},
}

GEMINI_MODELS = {
    # Gemini 2.5 Series (최신)
    "gemini-2.5-pro": {"name": "Gemini 2.5 Pro (최신)", "cost_per_1k_input": 1.25, "cost_per_1k_output": 5.0},
    "gemini-2.5-flash": {"name": "Gemini 2.5 Flash", "cost_per_1k_input": 0.075, "cost_per_1k_output": 0.30},
    "gemini-2.5-flash-lite": {"name": "Gemini 2.5 Flash-Lite", "cost_per_1k_input": 0.0375, "cost_per_1k_output": 0.15},

    # Gemini 2.0 Series
    "gemini-2.0-flash-exp": {"name": "Gemini 2.0 Flash Exp (무료)", "cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0},
    "gemini-2.0-flash": {"name": "Gemini 2.0 Flash", "cost_per_1k_input": 0.05, "cost_per_1k_output": 0.20},

    # Gemini 1.5 Series
    "gemini-1.5-pro": {"name": "Gemini 1.5 Pro", "cost_per_1k_input": 1.25, "cost_per_1k_output": 5.0},
    "gemini-1.5-flash": {"name": "Gemini 1.5 Flash", "cost_per_1k_input": 0.075, "cost_per_1k_output": 0.30},
}

# 사용 가능한 프롬프트 스타일
PROMPT_STYLES = [
    "original",
    "minimal",
    "coach",
    "scientist",
    "cbt",
    "narrative",
    "dashboard",
    "metacognitive",
    "public"
]


def show_section_title_with_tooltip(title: str, tooltip: str):
    """
    호버 시 툴팁이 나타나는 섹션 제목 표시

    Args:
        title: 섹션 제목
        tooltip: 호버 시 나타날 툴팁 텍스트
    """
    st.markdown(TOOLTIP_CSS, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="chart-title-tooltip">
        {title}
        <span class="tooltiptext">{tooltip}</span>
    </div>
    """, unsafe_allow_html=True)


def get_weekday_korean(date_str: str) -> str:
    """
    날짜 문자열에서 한글 요일을 반환합니다.

    Args:
        date_str: YYYY-MM-DD 형식의 날짜 문자열

    Returns:
        한글 요일 (월, 화, 수, 목, 금, 토, 일)
    """
    weekday_map = {
        0: '월', 1: '화', 2: '수', 3: '목',
        4: '금', 5: '토', 6: '일'
    }
    date_obj = pd.to_datetime(date_str)
    return weekday_map[date_obj.weekday()]


# 페이지 설정
st.set_page_config(
    page_title="일별 활동 리포트 (실험)",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_daily_data(date_str: str, apply_privacy_filter: bool = False) -> pd.DataFrame:
    """
    특정 날짜의 CleanedCalendarDocument를 로드하여 DataFrame으로 변환.

    Args:
        date_str: 날짜 (YYYY-MM-DD)
        apply_privacy_filter: 프라이버시 필터 적용 여부
    """
    try:
        docs = list(CleanedCalendarDocument.bulk_find(ref_date=date_str))

        if not docs:
            return None

        data = []
        for doc in docs:
            metadata = doc.metadata
            data.append({
                'original_id': str(doc.original_id),
                'start_datetime': pd.to_datetime(metadata.get('start_datetime')),
                'end_datetime': pd.to_datetime(metadata.get('end_datetime')),
                'duration_minutes': metadata.get('duration_minutes', 0),
                'category_name': metadata.get('category_name'),
                'calendar_name': metadata.get('category_name'),
                'event_name': metadata.get('event_name'),
                'notes': metadata.get('notes', ''),
                'sub_category': metadata.get('sub_category', ''),
                'learning_method': metadata.get('learning_method'),
                'learning_target': metadata.get('learning_target'),
                'work_tags': metadata.get('work_tags', []),
                'exercise_type': metadata.get('exercise_type'),
                'is_risky_recharger': metadata.get('is_risky_recharger', False),
                'has_relationship_tag': metadata.get('has_relationship_tag', False),
                'has_emotion_event': metadata.get('has_emotion_event', False),
            })

        df = pd.DataFrame(data)
        df = df.sort_values('start_datetime').reset_index(drop=True)

        # 프라이버시 필터 적용 (선택적)
        if apply_privacy_filter:
            df = apply_public_privacy_filter(
                df,
                days=7,
                ref_date=date_str,
                mask_notes=True,
                anonymize_names=True
            )

        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {str(e)}")
        return None


def load_weekly_data(start_date: str, end_date: str, apply_privacy_filter: bool = False) -> pd.DataFrame:
    """
    특정 기간의 CleanedCalendarDocument를 로드하여 DataFrame으로 변환.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
        apply_privacy_filter: 프라이버시 필터 적용 여부
    """
    try:
        # 날짜 범위 내 모든 문서 수집
        all_docs = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            docs = list(CleanedCalendarDocument.bulk_find(ref_date=date_str))
            all_docs.extend(docs)
            current_date += timedelta(days=1)

        if not all_docs:
            return None

        data = []
        for doc in all_docs:
            metadata = doc.metadata
            data.append({
                'original_id': str(doc.original_id),
                'ref_date': doc.ref_date,
                'start_datetime': pd.to_datetime(metadata.get('start_datetime')),
                'end_datetime': pd.to_datetime(metadata.get('end_datetime')),
                'duration_minutes': metadata.get('duration_minutes', 0),
                'category_name': metadata.get('category_name'),
                'calendar_name': metadata.get('category_name'),
                'event_name': metadata.get('event_name'),
                'notes': metadata.get('notes', ''),
                'sub_category': metadata.get('sub_category', ''),
                'learning_method': metadata.get('learning_method'),
                'learning_target': metadata.get('learning_target'),
                'work_tags': metadata.get('work_tags', []),
                'exercise_type': metadata.get('exercise_type'),
                'is_risky_recharger': metadata.get('is_risky_recharger', False),
                'has_relationship_tag': metadata.get('has_relationship_tag', False),
                'has_emotion_event': metadata.get('has_emotion_event', False),
            })

        df = pd.DataFrame(data)
        df = df.sort_values('start_datetime').reset_index(drop=True)

        # 프라이버시 필터 적용 (선택적)
        if apply_privacy_filter:
            df = apply_public_privacy_filter(
                df,
                days=7,
                ref_date=end_date,
                mask_notes=True,
                anonymize_names=True
            )

        return df
    except Exception as e:
        st.error(f"주간 데이터 로드 중 오류 발생: {str(e)}")
        return None


def load_monthly_data(year: int, month: int, apply_privacy_filter: bool = False) -> pd.DataFrame:
    """
    특정 월의 CleanedCalendarDocument를 로드하여 DataFrame으로 변환.

    Args:
        year: 연도 (YYYY)
        month: 월 (1-12)
        apply_privacy_filter: 프라이버시 필터 적용 여부
    """
    try:
        # 월의 시작일과 종료일 계산
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # 날짜 범위 내 모든 문서 수집
        all_docs = []
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            docs = list(CleanedCalendarDocument.bulk_find(ref_date=date_str))
            all_docs.extend(docs)
            current_date += timedelta(days=1)

        if not all_docs:
            return None

        data = []
        for doc in all_docs:
            metadata = doc.metadata
            data.append({
                'original_id': str(doc.original_id),
                'ref_date': doc.ref_date,
                'start_datetime': pd.to_datetime(metadata.get('start_datetime')),
                'end_datetime': pd.to_datetime(metadata.get('end_datetime')),
                'duration_minutes': metadata.get('duration_minutes', 0),
                'category_name': metadata.get('category_name'),
                'calendar_name': metadata.get('category_name'),
                'event_name': metadata.get('event_name'),
                'notes': metadata.get('notes', ''),
                'sub_category': metadata.get('sub_category', ''),
                'learning_method': metadata.get('learning_method'),
                'learning_target': metadata.get('learning_target'),
                'work_tags': metadata.get('work_tags', []),
                'exercise_type': metadata.get('exercise_type'),
                'is_risky_recharger': metadata.get('is_risky_recharger', False),
                'has_relationship_tag': metadata.get('has_relationship_tag', False),
                'has_emotion_event': metadata.get('has_emotion_event', False),
            })

        df = pd.DataFrame(data)
        df = df.sort_values('start_datetime').reset_index(drop=True)

        # 프라이버시 필터 적용 (선택적)
        if apply_privacy_filter:
            df = apply_public_privacy_filter(
                df,
                days=30,
                ref_date=end_str,
                mask_notes=True,
                anonymize_names=True
            )

        return df
    except Exception as e:
        st.error(f"월간 데이터 로드 중 오류 발생: {str(e)}")
        return None


def show_statistics(df: pd.DataFrame, target_date: str, is_weekly: bool = False, start_date: str = None, end_date: str = None):
    """전체 통계 표시"""
    if is_weekly and start_date and end_date:
        st.subheader(f"📊 주간 통계: {start_date} ~ {end_date}")
    else:
        weekday = get_weekday_korean(target_date)
        st.subheader(f"📊 {target_date} ({weekday}) 전체 통계")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("총 기록 시간", format_duration(df['duration_minutes'].sum()))

    with col2:
        st.metric("총 활동 수", f"{len(df)}개")

    with col3:
        st.metric("#인간관계", f"{df['has_relationship_tag'].sum()}개")

    with col4:
        st.metric("#즉시만족", f"{df['is_risky_recharger'].sum()}개")


def show_agency_pie_chart(df: pd.DataFrame):
    """Agency 파이차트 표시 (Interactive)"""
    show_section_title_with_tooltip(
        "🎯 Agency 파이차트",
        "💡 Tip: 호버하면 실제 영역별 합계 시간을 확인할 수 있습니다!"
    )

    fig = plot_agency_pie_chart_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  Agency 데이터가 없습니다.")


def show_category_distribution(df: pd.DataFrame):
    """카테고리별 시간 분포 표시 (Interactive)"""
    show_section_title_with_tooltip(
        "📈 카테고리별 시간 분포",
        "💡 Tip: 바를 호버하면 하루 기준 퍼센티지를 확인할 수 있습니다! 과도하게 회복에 많이 사용될경우 빨간색으로 표시됩니다"
    )

    fig = plot_category_distribution_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  카테고리 데이터가 없습니다.")


def show_sleep_breakdown(df: pd.DataFrame):
    """수면 상세 분석 표시 (Interactive)"""
    show_section_title_with_tooltip(
        "😴 수면 상세 분석",
        "💡 Tip: 바를 호버하면 각 수면 이벤트의 메모를 확인할 수 있습니다!"
    )

    fig = plot_sleep_breakdown_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  수면 데이터가 없습니다.")


def show_five_areas_analysis(df: pd.DataFrame):
    """5개 영역 상세 분석 (Interactive Plotly)"""

    # 1. 일/생산
    show_section_title_with_tooltip(
        "💼 일/생산",
        "💡 Tip: 바를 호버하면 메모와 상세 정보를 확인할 수 있습니다!"
    )
    fig = plot_work_by_event_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  일/생산 데이터가 없습니다.")

    st.markdown("---")

    # 2. 학습/성장
    show_section_title_with_tooltip(
        "📚 학습/성장 ",
        "💡 Tip: 바를 호버하면 메모와 상세 정보를 확인할 수 있습니다!"
    )
    fig = plot_learning_by_event_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  학습/성장 데이터가 없습니다.")

    st.markdown("---")

    # 3. 재충전 활동
    show_section_title_with_tooltip(
        "🌴 휴식/회복 ",
        "💡 Tip: 바를 호버하면 메모와 상세 정보를 확인할 수 있습니다!"
    )
    fig = plot_recharge_by_event_interactive(df, top_n=15, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  재충전 활동 데이터가 없습니다.")

    st.markdown("---")

    # 4. Drain
    show_section_title_with_tooltip(
        "⚠️ Drain",
        "💡 Tip: 바를 호버하면 메모와 상세 정보를 확인할 수 있습니다!"
    )
    fig = plot_drain_by_event_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  Drain 데이터가 없습니다.")

    st.markdown("---")

    # 5. 일상 관리

    show_section_title_with_tooltip(
        "🏠 유지/정리",
        "💡 Tip: 바를 호버하면 메모와 상세 정보를 확인할 수 있습니다!"
    )
    fig = plot_maintenance_by_event_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  유지/정리 데이터가 없습니다.")

    st.markdown("---")

    # 6. #인간관계 태그 - Agency별
    show_section_title_with_tooltip(
        "👥 인간관계 - Agency별 분포",
        "💡 Tip: 바를 호버하면 메모와 상세 정보를 확인할 수 있습니다!"
    )
    fig = plot_relationship_by_agency_interactive(df, show_title=False)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  #인간관계 태그 데이터가 없습니다.")


def generate_feedback_with_metrics(
    date_str: str,
    provider: str,
    model_id: str,
    temperature: float,
    prompt_style: str,
) -> tuple[str, dict]:
    """
    피드백을 생성하고 성능 메트릭을 반환합니다.

    Args:
        date_str: 날짜
        provider: 모델 제공자 (OpenAI / Gemini)
        model_id: 모델 ID
        temperature: 온도
        prompt_style: 프롬프트 스타일

    Returns:
        (피드백 내용, 메트릭 딕셔너리)
    """
    try:
        # Provider에 따라 DailyFeedbackGenerator 또는 커스텀 생성
        if provider == "OpenAI":
            # GPT-5, GPT-4.1 시리즈는 temperature를 지원하지 않거나 기본값(1.0)만 지원
            # 이런 모델들은 temperature를 None으로 설정하거나 기본값 사용
            temperature_restricted_models = [
                "gpt-5", "gpt-5.1", "gpt-5-pro", "gpt-5-mini", "gpt-5-nano",
                "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"
            ]

            if model_id in temperature_restricted_models:
                # temperature를 전달하지 않음 (기본값 사용)
                generator = DailyFeedbackGenerator(
                    model_id=model_id,
                    temperature=1.0,  # 기본값 사용
                    prompt_style=prompt_style
                )
                actual_temperature = 1.0
            else:
                generator = DailyFeedbackGenerator(
                    model_id=model_id,
                    temperature=temperature,
                    prompt_style=prompt_style
                )
                actual_temperature = temperature

            start_time = time.time()

            feedback_content = generator.generate(
                target_date=date_str,
                include_previous=True,
                include_next=True,
                save_to_db=False  # 실험용이므로 DB에 저장 안 함
            )

            end_time = time.time()
            generation_time = end_time - start_time

            # 메트릭 계산 (대략적)
            input_tokens = len(feedback_content) // 4  # 대략적 추정
            output_tokens = len(feedback_content) // 4

            model_info = OPENAI_MODELS.get(model_id, {})
            cost = (
                input_tokens / 1000 * model_info.get("cost_per_1k_input", 0) +
                output_tokens / 1000 * model_info.get("cost_per_1k_output", 0)
            )

        else:  # Gemini
            import google.generativeai as genai
            from llm_engineering.settings import Settings
            from llm_engineering.application.feedback.daily.prompts import get_prompt
            from llm_engineering.application.feedback.document_loader import DocumentLoader

            settings = Settings.load_settings()

            # Gemini API 설정
            genai.configure(api_key=settings.GOOGLE_API_KEY)

            # 문서 로드
            docs = DocumentLoader.load_with_context(
                target_date=date_str,
                include_previous=True,
                include_next=True,
            )

            # 컨텍스트 포맷팅 (간단한 버전 - 시간순 정렬)
            context_parts = []
            if docs.get("target"):
                context_parts.append(f"## 분석 대상일: {date_str}")

                # 시간순으로 정렬
                sorted_docs = sorted(
                    docs["target"],
                    key=lambda x: (
                        x.get("ref_date", ""),
                        x.get("metadata", {}).get("start_datetime", "")
                    )
                )

                for doc in sorted_docs:
                    platform = doc.get("platform", "unknown").upper()
                    content = doc.get("content", "")
                    ref_date = doc.get("ref_date", "N/A")
                    context_parts.append(f"### [{platform}] {ref_date}")
                    context_parts.append(content)
                    context_parts.append("")

            context = "\n".join(context_parts)

            # 프롬프트 생성
            system_prompt = get_prompt(prompt_style)
            full_prompt = f"{system_prompt}\n\n{context}"

            # Gemini 모델 초기화 및 생성
            model = genai.GenerativeModel(model_id)

            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
            )

            start_time = time.time()
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            feedback_content = response.text
            end_time = time.time()

            generation_time = end_time - start_time

            # 메트릭 계산 (대략적)
            input_tokens = len(context) // 4
            output_tokens = len(feedback_content) // 4

            model_info = GEMINI_MODELS.get(model_id, {})
            cost = (
                input_tokens / 1000 * model_info.get("cost_per_1k_input", 0) +
                output_tokens / 1000 * model_info.get("cost_per_1k_output", 0)
            )
            actual_temperature = temperature

        metrics = {
            "generation_time": generation_time,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": cost,
            "model_id": model_id,
            "provider": provider,
            "temperature": actual_temperature,
            "requested_temperature": temperature,
            "prompt_style": prompt_style,
        }

        return feedback_content, metrics

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return f"❌ 피드백 생성 중 오류 발생: {str(e)}\n\n{error_detail}", {}


def generate_monthly_feedback_with_metrics(
    year: int,
    month: int,
    provider: str,
    model_id: str,
    temperature: float,
    monthly_prompt_style: str = "original",
    df: pd.DataFrame = None,
) -> tuple[str, dict]:
    """
    월간 피드백을 생성하고 성능 메트릭을 반환합니다.

    Args:
        year: 연도
        month: 월
        provider: 모델 제공자 (OpenAI / Gemini)
        model_id: 모델 ID
        temperature: 온도
        monthly_prompt_style: 월간 프롬프트 스타일 ("original", "v2_weekly_based")
        df: 월간 데이터 DataFrame

    Returns:
        (피드백 내용, 메트릭 딕셔너리)
    """
    try:
        if provider == "OpenAI":
            # Temperature 제한 모델 처리
            temperature_restricted_models = [
                "gpt-5", "gpt-5.1", "gpt-5-pro", "gpt-5-mini", "gpt-5-nano",
                "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"
            ]

            if model_id in temperature_restricted_models:
                actual_temperature = 1.0
            else:
                actual_temperature = temperature

            start_time = time.time()

            if monthly_prompt_style == "v2_weekly_based":
                # V2: 주간 V2 리포트 기반 월간 요약
                feedback_content = _generate_monthly_from_weekly_v2(
                    year, month, model_id, actual_temperature, df
                )
            else:
                # Original or Public: 기존 계층적 요약 방식
                generator = MonthlyFeedbackGenerator(
                    model_id=model_id,
                    temperature=actual_temperature,
                    prompt_style=monthly_prompt_style if monthly_prompt_style != "v2_weekly_based" else "original",
                )
                feedback_content = generator.generate(
                    year=year,
                    month=month,
                )

            end_time = time.time()
            generation_time = end_time - start_time

            # 메트릭 계산 (대략적)
            input_tokens = len(feedback_content) // 4
            output_tokens = len(feedback_content) // 4

            model_info = OPENAI_MODELS.get(model_id, {})
            cost = (
                input_tokens / 1000 * model_info.get("cost_per_1k_input", 0) +
                output_tokens / 1000 * model_info.get("cost_per_1k_output", 0)
            )

        else:  # Gemini
            import google.generativeai as genai
            from llm_engineering.settings import Settings

            settings = Settings.load_settings()

            # Gemini API 설정
            genai.configure(api_key=settings.GOOGLE_API_KEY)

            start_time = time.time()

            if monthly_prompt_style == "v2_weekly_based":
                # V2는 복잡한 체인이므로 OpenAI 권장
                raise ValueError("V2 스타일은 현재 OpenAI 모델에서만 지원됩니다. OpenAI를 선택해주세요.")
            else:
                # Original or Public: MonthlyFeedbackGenerator 사용
                generator = MonthlyFeedbackGenerator(
                    model_id=model_id,
                    temperature=temperature,
                    prompt_style=monthly_prompt_style if monthly_prompt_style != "v2_weekly_based" else "original",
                )
                feedback_content = generator.generate(
                    year=year,
                    month=month,
                )

            end_time = time.time()
            generation_time = end_time - start_time

            # 메트릭 계산 (대략적)
            input_tokens = len(feedback_content) // 4
            output_tokens = len(feedback_content) // 4

            model_info = GEMINI_MODELS.get(model_id, {})
            cost = (
                input_tokens / 1000 * model_info.get("cost_per_1k_input", 0) +
                output_tokens / 1000 * model_info.get("cost_per_1k_output", 0)
            )
            actual_temperature = temperature

        metrics = {
            "generation_time": generation_time,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": cost,
            "model_id": model_id,
            "provider": provider,
            "temperature": actual_temperature,
            "requested_temperature": temperature,
            "report_type": "monthly",
            "prompt_style": monthly_prompt_style,
        }

        return feedback_content, metrics

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return f"❌ 월간 피드백 생성 중 오류 발생: {str(e)}\n\n{error_detail}", {}


async def _generate_weekly_v2_report_async(
    week_num: int,
    week_start: str,
    week_end: str,
    week_df: pd.DataFrame,
    model_id: str,
    temperature: float,
    prompt_style: str = "v2",
) -> str:
    """
    단일 주간 V2 리포트를 비동기로 생성합니다.

    Args:
        week_num: 주 번호
        week_start: 주 시작 날짜
        week_end: 주 종료 날짜
        week_df: 해당 주의 데이터 DataFrame
        model_id: 모델 ID
        temperature: 온도
        prompt_style: 프롬프트 스타일 ("v2" 또는 "v2_public")

    Returns:
        주간 V2 리포트 문자열
    """
    from llm_engineering.application.feedback.weekly.generator import WeeklyFeedbackGenerator
    from llm_engineering.application.feedback.weekly.metrics import compute_weekly_metrics
    from loguru import logger

    if week_df.empty:
        return f"### Week {week_num}: {week_start} ~ {week_end}\n\n데이터 없음\n\n---"

    logger.info(f"Generating {prompt_style} report for Week {week_num}: {week_start} ~ {week_end}")

    # 주간 메트릭 계산
    week_metrics = compute_weekly_metrics(week_df, week_start, week_end)

    # 주간 V2 리포트 생성 (비동기)
    generator = WeeklyFeedbackGenerator(
        model_id=model_id,
        temperature=temperature,
        prompt_style=prompt_style,
    )

    # generate 메서드를 비동기로 호출할 수 없으므로, 내부 로직을 직접 비동기로 처리
    from llm_engineering.application.feedback.document_loader import DocumentLoader
    from langchain_core.messages import HumanMessage

    # 주간 데이터 로드
    weekly_docs = DocumentLoader.load_by_date_range(
        start_date=week_start,
        end_date=week_end,
        sources=["calendar", "notion", "naver_blog"],
        include_weekly_reports=False,
    )

    # 컨텍스트 포맷팅
    context = generator._format_v2_context(
        week_start, week_end, weekly_docs, [], week_metrics
    )

    # LLM 비동기 호출
    response = await generator.llm.ainvoke([HumanMessage(content=context)])
    week_feedback = response.content

    # JSON 부분 제거
    week_feedback_clean = WeeklyFeedbackGenerator.remove_json_section(week_feedback)

    logger.info(f"Week {week_num} V2 report generated ({len(week_feedback_clean)} chars)")

    return f"### Week {week_num}: {week_start} ~ {week_end}\n\n{week_feedback_clean}\n\n---"


async def _generate_all_weekly_v2_reports_async(
    weeks: list[tuple[str, str]],
    df: pd.DataFrame,
    model_id: str,
    temperature: float,
    prompt_style: str = "v2",
) -> list[str]:
    """
    모든 주간 V2 리포트를 병렬로 생성합니다.

    Args:
        weeks: [(week_start, week_end), ...] 리스트
        df: 월간 데이터 DataFrame
        model_id: 모델 ID
        temperature: 온도
        prompt_style: 프롬프트 스타일 ("v2" 또는 "v2_public")

    Returns:
        주간 V2 리포트 리스트
    """
    import asyncio
    from loguru import logger

    tasks = []
    for week_num, (week_start, week_end) in enumerate(weeks, 1):
        # 해당 주의 데이터 필터링
        week_df = df[
            (df['ref_date'] >= week_start) &
            (df['ref_date'] <= week_end)
        ]

        task = _generate_weekly_v2_report_async(
            week_num, week_start, week_end, week_df, model_id, temperature, prompt_style
        )
        tasks.append(task)

    logger.info(f"Starting parallel generation of {len(tasks)} weekly V2 reports")
    reports = await asyncio.gather(*tasks)
    logger.info(f"Completed parallel generation of {len(reports)} weekly V2 reports")

    return reports


def _generate_monthly_from_weekly_v2(
    year: int,
    month: int,
    model_id: str,
    temperature: float,
    df: pd.DataFrame,
    prompt_style: str = "v2",
) -> str:
    """
    주간 V2 리포트를 병렬로 생성한 후 이를 기반으로 월간 요약을 생성합니다.

    Args:
        year: 연도
        month: 월
        model_id: 모델 ID
        temperature: 온도
        df: 월간 데이터 DataFrame
        prompt_style: 프롬프트 스타일 ("v2" 또는 "v2_public")

    Returns:
        월간 피드백 문자열
    """
    import asyncio
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    # 1. 월을 주별로 분할
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    weeks = []
    current = start_date
    while current <= end_date:
        week_start = current - timedelta(days=current.weekday())
        week_end = week_start + timedelta(days=6)

        if week_start < start_date:
            week_start = start_date
        if week_end > end_date:
            week_end = end_date

        weeks.append((week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")))
        current = week_end + timedelta(days=1)

    # 주간 리포트 스타일 결정
    weekly_style = "v2_public" if prompt_style == "v2_public" else "v2"

    # 2. 각 주별 V2 리포트 병렬 생성
    weekly_v2_reports = asyncio.run(
        _generate_all_weekly_v2_reports_async(weeks, df, model_id, temperature, weekly_style)
    )

    # 3. 주간 V2 리포트들을 종합하여 월간 피드백 생성
    if prompt_style == "v2_public":
        # Public 버전: 개인정보 보호 정책 포함
        monthly_prompt = f"""당신은 **공개 배포용** 월간 행동 패턴 분석 전문가입니다.

**PRIVACY PROTECTION POLICY:**

1. **Personal Information Protection:**
   - ❌ NO people names, places, organization names
   - ❌ NO relationship details beyond time allocation
   - ❌ NO sensitive personal context

2. **Content Disclosure Rules:**
   - ✅ PUBLIC: Work/production, Learning/growth patterns
   - ⚠️ LIMITED: Recharge, Maintenance - **time only**
   - ❌ PRIVATE: Relationship specifics, personal contexts

3. **Analysis Focus:**
   - Generic behavioral patterns and trends
   - Anonymized triggers and contexts
   - Privacy-safe recommendations

아래는 {year}년 {month}월의 주별 V2 리포트들입니다.
각 주간 리포트는 이미 사전 계산된 메트릭을 기반으로 작성되었으며, 패턴 분석과 대표 태그를 포함합니다.
**모든 리포트는 개인정보 보호 정책을 따라 작성되었습니다.**

당신의 임무는 이 주간 리포트들을 종합하여 **월간 트렌드**, **반복 패턴**, **장기적 통찰**을 제공하되,
**개인정보를 철저히 보호**하는 것입니다.

## 주간 리포트들

{"".join(weekly_v2_reports)}

## 출력 형식 (Privacy-Protected)

다음 구조로 월간 피드백을 작성하세요:

## 월간 피드백 ({year}년 {month}월)

[이번 달을 한 문장으로 요약 - 개인정보 제외]

---

### 📊 월간 트렌드 분석

**주별 추이**:
- Week 1: [일반화된 핵심 패턴]
- Week 2: [일반화된 핵심 패턴]
- Week 3: [일반화된 핵심 패턴]
- Week 4: [일반화된 핵심 패턴]

**전체 트렌드**: [개선/안정/하락 등, 구체적이되 개인 맥락 제외]

---

### 🔄 반복 패턴 식별

**긍정적 패턴 (지속해야 할 것)**:
[여러 주에 걸쳐 반복된 일반화된 긍정적 패턴 2-3개]

**부정적 패턴 (개선이 필요한 것)**:
[여러 주에 걸쳐 반복된 일반화된 부정적 패턴 2-3개]

---

### 🎯 이번 달 주요 성과

[월간 관점에서 의미 있는 성과 3-4개, 일반화된 설명]

---

### ⚠️ 지속적 문제

[매주 반복되거나 해결되지 않은 행동 문제들, 개인 맥락 제외]

---

### 💡 다음 달 개선 전략

[이번 달 패턴을 기반으로 한 구체적이되 일반화된 전략 3개]

---

## PRIVACY RULES

- **Remove ALL personal identifiers** (names, places, organizations)
- **Anonymize all contexts** (use generic terms like "지인", "모임")
- **Time-only for sensitive categories** (relationships, personal activities)
- **Focus on behavioral patterns**, not personal stories
- **Ensure report is safe for public distribution**

**톤**: 장기적 관점, 패턴 중심, 전략적, 균형적, **공개 가능**
"""
    else:
        # Original V2 버전
        monthly_prompt = f"""당신은 월간 행동 패턴 분석 전문가입니다.

아래는 {year}년 {month}월의 주별 V2 리포트들입니다.
각 주간 리포트는 이미 사전 계산된 메트릭을 기반으로 작성되었으며, 패턴 분석과 대표 태그를 포함합니다.

당신의 임무는 이 주간 리포트들을 종합하여 **월간 트렌드**, **반복 패턴**, **장기적 통찰**을 제공하는 것입니다.

## 주간 리포트들

{"".join(weekly_v2_reports)}

## 출력 형식

다음 구조로 월간 피드백을 작성하세요:

## 월간 피드백 ({year}년 {month}월)

[이번 달을 한 문장으로 요약]

---

### 📊 월간 트렌드 분석

**주별 추이**:
- Week 1: [핵심 패턴]
- Week 2: [핵심 패턴]
- Week 3: [핵심 패턴]
- Week 4: [핵심 패턴]

**전체 트렌드**: [개선/안정/하락 등, 구체적으로]

---

### 🔄 반복 패턴 식별

**긍정적 패턴 (지속해야 할 것)**:
[여러 주에 걸쳐 반복된 긍정적 패턴 2-3개]

**부정적 패턴 (개선이 필요한 것)**:
[여러 주에 걸쳐 반복된 부정적 패턴 2-3개]

---

### 🎯 이번 달 주요 성과

[월간 관점에서 의미 있는 성과 3-4개]

---

### ⚠️ 지속적 문제

[매주 반복되거나 해결되지 않은 문제들]

---

### 💡 다음 달 개선 전략

[이번 달 패턴을 기반으로 한 구체적 전략 3개]

---

**톤**: 장기적 관점, 패턴 중심, 전략적, 균형적
"""

    # LLM 호출
    from llm_engineering.settings import Settings
    settings = Settings.load_settings()

    llm = ChatOpenAI(
        model=model_id,
        temperature=temperature,
        openai_api_key=settings.OPENAI_API_KEY
    )
    response = llm.invoke([HumanMessage(content=monthly_prompt)])

    return response.content


def generate_weekly_feedback_with_metrics(
    start_date: str,
    end_date: str,
    provider: str,
    model_id: str,
    temperature: float,
    weekly_prompt_style: str = "original",
    df: pd.DataFrame = None,
) -> tuple[str, dict]:
    """
    주간 피드백을 생성하고 성능 메트릭을 반환합니다.

    Args:
        start_date: 시작 날짜
        end_date: 종료 날짜
        provider: 모델 제공자 (OpenAI / Gemini)
        model_id: 모델 ID
        temperature: 온도
        weekly_prompt_style: 주간 프롬프트 스타일 ("original", "v2")
        df: 주간 데이터 DataFrame (V2 스타일에서 메트릭 계산용)

    Returns:
        (피드백 내용, 메트릭 딕셔너리)
    """
    try:
        # V2/V3/V2_PUBLIC 스타일일 때 사전 계산된 메트릭 준비
        precomputed_metrics = None
        if weekly_prompt_style in ["v2", "v3", "v2_public"] and df is not None:
            from llm_engineering.application.feedback.weekly.metrics import compute_weekly_metrics
            precomputed_metrics = compute_weekly_metrics(df, start_date, end_date)

        if provider == "OpenAI":
            # Temperature 제한 모델 처리
            temperature_restricted_models = [
                "gpt-5", "gpt-5.1", "gpt-5-pro", "gpt-5-mini", "gpt-5-nano",
                "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"
            ]

            if model_id in temperature_restricted_models:
                generator = WeeklyFeedbackGenerator(
                    model_id=model_id,
                    temperature=1.0,
                    prompt_style=weekly_prompt_style,
                )
                actual_temperature = 1.0
            else:
                generator = WeeklyFeedbackGenerator(
                    model_id=model_id,
                    temperature=temperature,
                    prompt_style=weekly_prompt_style,
                )
                actual_temperature = temperature

            start_time = time.time()

            feedback_content = generator.generate(
                start_date=start_date,
                end_date=end_date,
                include_past_reports=True,
                past_reports_limit=4,
                precomputed_metrics=precomputed_metrics,
                save_to_db=False  # 실험용이므로 DB에 저장 안 함
            )

            end_time = time.time()
            generation_time = end_time - start_time

            # 메트릭 계산 (대략적)
            input_tokens = len(feedback_content) // 4
            output_tokens = len(feedback_content) // 4

            model_info = OPENAI_MODELS.get(model_id, {})
            cost = (
                input_tokens / 1000 * model_info.get("cost_per_1k_input", 0) +
                output_tokens / 1000 * model_info.get("cost_per_1k_output", 0)
            )

        else:  # Gemini
            import google.generativeai as genai
            from llm_engineering.settings import Settings
            from llm_engineering.application.feedback.weekly.prompts import WEEKLY_FEEDBACK_PROMPT, get_weekly_prompt
            from llm_engineering.application.feedback.document_loader import DocumentLoader
            import json

            settings = Settings.load_settings()

            # Gemini API 설정
            genai.configure(api_key=settings.GOOGLE_API_KEY)

            # 주간 문서 로드
            weekly_docs = DocumentLoader.load_by_date_range(
                start_date=start_date,
                end_date=end_date,
                sources=["calendar", "notion", "naver_blog"],
                include_weekly_reports=False,
            )

            # 컨텍스트 포맷팅
            context_parts = []
            context_parts.append(f"## 주간 분석 대상: {start_date} ~ {end_date}")
            context_parts.append("")

            if weekly_docs:
                # 날짜별로 그룹화
                docs_by_date = {}
                for doc in weekly_docs:
                    ref_date = doc.get("ref_date", "unknown")
                    if ref_date not in docs_by_date:
                        docs_by_date[ref_date] = []
                    docs_by_date[ref_date].append(doc)

                for date in sorted(docs_by_date.keys()):
                    day_docs = docs_by_date[date]
                    context_parts.append(f"### {date}")
                    for doc in day_docs:
                        platform = doc.get("platform", "unknown").upper()
                        content = doc.get("content", "")
                        context_parts.append(f"[{platform}] {content}")
                    context_parts.append("")

            context = "\n".join(context_parts)

            # 프롬프트 스타일에 따른 처리
            if weekly_prompt_style == "v3":
                # V3는 2단계 체인이므로 Gemini에서는 지원하지 않음
                raise ValueError("V3 스타일은 현재 OpenAI 모델에서만 지원됩니다. OpenAI를 선택해주세요.")
            elif weekly_prompt_style == "v2" and precomputed_metrics:
                # V2: 사전 계산된 메트릭 포함
                prompt_template = get_weekly_prompt("v2")
                full_prompt = prompt_template.format(
                    start_date=start_date,
                    end_date=end_date,
                    precomputed_metrics=json.dumps(precomputed_metrics, ensure_ascii=False, indent=2),
                    raw_logs=context,
                    previous_week_summary="없음",
                )
            else:
                # Original: 기존 방식
                full_prompt = f"{WEEKLY_FEEDBACK_PROMPT}\n\n{context}"

            # Gemini 모델 초기화 및 생성
            model = genai.GenerativeModel(model_id)

            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
            )

            start_time = time.time()
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            feedback_content = response.text
            end_time = time.time()

            generation_time = end_time - start_time

            # 메트릭 계산 (대략적)
            input_tokens = len(context) // 4
            output_tokens = len(feedback_content) // 4

            model_info = GEMINI_MODELS.get(model_id, {})
            cost = (
                input_tokens / 1000 * model_info.get("cost_per_1k_input", 0) +
                output_tokens / 1000 * model_info.get("cost_per_1k_output", 0)
            )
            actual_temperature = temperature

        metrics = {
            "generation_time": generation_time,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": cost,
            "model_id": model_id,
            "provider": provider,
            "temperature": actual_temperature,
            "requested_temperature": temperature,
            "report_type": "weekly",
            "prompt_style": weekly_prompt_style,
        }

        return feedback_content, metrics

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return f"❌ 주간 피드백 생성 중 오류 발생: {str(e)}\n\n{error_detail}", {}


def show_llm_feedback_experiment(date_str: str, provider: str, model_id: str, temperature: float, prompt_style: str):
    """실험용 LLM 피드백 영역 (일별)"""

    # 모델 정보 가져오기
    if provider == "OpenAI":
        model_info = OPENAI_MODELS.get(model_id, {})
    else:
        model_info = GEMINI_MODELS.get(model_id, {})

    model_name = model_info.get("name", model_id)

    st.caption(f"🧪 실험 모드 - {provider}: {model_name}, Temperature: {temperature}, 스타일: {prompt_style}")

    # 피드백 생성 버튼
    if st.button("🚀 피드백 생성", type="primary", use_container_width=True):
        with st.spinner("피드백 생성 중..."):
            feedback, metrics = generate_feedback_with_metrics(
                date_str, provider, model_id, temperature, prompt_style
            )

            if metrics:
                # 메트릭 표시
                st.success("✅ 피드백이 생성되었습니다!")

                # Temperature 조정 경고
                if metrics.get("temperature") != metrics.get("requested_temperature"):
                    st.warning(f"⚠️ 이 모델은 temperature 조정을 지원하지 않습니다. 기본값 {metrics['temperature']}이(가) 사용되었습니다.")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("생성 시간", f"{metrics['generation_time']:.2f}s")
                with col2:
                    st.metric("총 토큰", f"{metrics['total_tokens']:,}")
                with col3:
                    st.metric("예상 비용", f"${metrics['estimated_cost']:.4f}")
                with col4:
                    st.metric("Temperature", f"{metrics['temperature']}")

            st.markdown("---")
            st.markdown("### 📋 일일 피드백")
            st.markdown(feedback)
    else:
        st.info(f"""
        **🧪 실험용 대시보드 - {provider}**

        다양한 모델과 설정을 테스트할 수 있습니다:
        - 왼쪽 사이드바에서 Provider 선택 (OpenAI / Gemini)
        - 모델 선택 ({len(OPENAI_MODELS if provider == 'OpenAI' else GEMINI_MODELS)}개 모델)
        - Temperature 조정 (0.0~1.0)
        - 프롬프트 스타일 변경
        - 프라이버시 필터 on/off

        위 버튼을 클릭하여 피드백을 생성하세요.
        """)


def show_monthly_llm_feedback_experiment(
    year: int,
    month: int,
    provider: str,
    model_id: str,
    temperature: float,
    monthly_prompt_style: str = "original",
    df: pd.DataFrame = None
):
    """실험용 LLM 피드백 영역 (월간)"""

    # 모델 정보 가져오기
    if provider == "OpenAI":
        model_info = OPENAI_MODELS.get(model_id, {})
    else:
        model_info = GEMINI_MODELS.get(model_id, {})

    model_name = model_info.get("name", model_id)

    style_labels = {
        "original": "Original (계층적)",
        "v2_weekly_based": "V2 (주간 V2 기반)"
    }
    style_label = style_labels.get(monthly_prompt_style, "Original")
    st.caption(f"🧪 월간 실험 모드 - {provider}: {model_name}, Temperature: {temperature}, 스타일: {style_label}")

    # 피드백 생성 버튼
    if st.button("🚀 월간 피드백 생성", type="primary", use_container_width=True):
        with st.spinner(f"월간 피드백 생성 중... ({year}년 {month}월 데이터를 분석합니다. 시간이 걸릴 수 있습니다.)"):
            feedback, metrics = generate_monthly_feedback_with_metrics(
                year, month, provider, model_id, temperature,
                monthly_prompt_style=monthly_prompt_style,
                df=df
            )

            if metrics:
                # 메트릭 표시
                st.success("✅ 월간 피드백이 생성되었습니다!")

                # Temperature 조정 경고
                if metrics.get("temperature") != metrics.get("requested_temperature"):
                    st.warning(f"⚠️ 이 모델은 temperature 조정을 지원하지 않습니다. 기본값 {metrics['temperature']}이(가) 사용되었습니다.")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("생성 시간", f"{metrics['generation_time']:.2f}s")
                with col2:
                    st.metric("총 토큰", f"{metrics['total_tokens']:,}")
                with col3:
                    st.metric("예상 비용", f"${metrics['estimated_cost']:.4f}")
                with col4:
                    st.metric("프롬프트", metrics.get('prompt_style', 'original'))

            st.markdown("---")
            st.markdown(f"### 📋 월간 피드백 ({year}년 {month}월)")
            st.markdown(feedback)
    else:
        st.info(f"""
        **🧪 월간 실험용 대시보드 - {provider}**

        한 달간의 데이터를 분석하여 월간 피드백을 생성합니다:
        - 기간: {year}년 {month}월
        - 모델: {model_name}
        - 프롬프트 스타일: {style_label}

        **Original 스타일:**
        - 주별 요약 후 월간 피드백 생성 (계층적 요약)

        **V2 스타일 (실험):**
        - 각 주별로 V2 리포트 생성 (사전계산 메트릭 + 패턴 분석)
        - 주간 V2 리포트들을 종합하여 월간 트렌드 분석
        - 더 정확하지만 시간과 비용이 많이 듦

        위 버튼을 클릭하여 월간 피드백을 생성하세요.
        """)


def show_weekly_llm_feedback_experiment(
    start_date: str,
    end_date: str,
    provider: str,
    model_id: str,
    temperature: float,
    weekly_prompt_style: str = "original",
    df: pd.DataFrame = None
):
    """실험용 LLM 피드백 영역 (주간)"""

    # 모델 정보 가져오기
    if provider == "OpenAI":
        model_info = OPENAI_MODELS.get(model_id, {})
    else:
        model_info = GEMINI_MODELS.get(model_id, {})

    model_name = model_info.get("name", model_id)

    style_labels = {
        "original": "Original",
        "v2": "V2 (사전계산)",
        "v3": "V3 (2단계 체인)"
    }
    style_label = style_labels.get(weekly_prompt_style, "Original")
    st.caption(f"🧪 주간 실험 모드 - {provider}: {model_name}, Temperature: {temperature}, 스타일: {style_label}")

    # V2/V3/V2_PUBLIC 스타일일 때 사전 계산된 메트릭 미리보기
    if weekly_prompt_style in ["v2", "v3", "v2_public"] and df is not None:
        with st.expander("📊 사전 계산된 메트릭 미리보기"):
            from llm_engineering.application.feedback.weekly.metrics import compute_weekly_metrics
            precomputed = compute_weekly_metrics(df, start_date, end_date)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 시간", f"{precomputed['summary']['total_hours']}h")
                st.metric("활동 수", precomputed['summary']['total_activities'])
            with col2:
                st.metric("평균 수면", f"{precomputed['sleep']['avg_h']}h")
                recovery = precomputed.get('recovery_ratio')
                st.metric("회복 비율", f"{recovery}" if recovery else "N/A (Drain 없음)")
            with col3:
                st.metric("Drain%", f"{precomputed['drain']['drain_percent']}%")
                st.metric("심야 Drain", f"{precomputed['drain']['late_night_minutes_23_03']}분")

    # 피드백 생성 버튼
    if st.button("🚀 주간 피드백 생성", type="primary", use_container_width=True):
        with st.spinner("주간 피드백 생성 중... (7일간의 데이터를 분석합니다)"):
            feedback, metrics = generate_weekly_feedback_with_metrics(
                start_date, end_date, provider, model_id, temperature,
                weekly_prompt_style=weekly_prompt_style,
                df=df
            )

            if metrics:
                # 메트릭 표시
                st.success("✅ 주간 피드백이 생성되었습니다!")

                # Temperature 조정 경고
                if metrics.get("temperature") != metrics.get("requested_temperature"):
                    st.warning(f"⚠️ 이 모델은 temperature 조정을 지원하지 않습니다. 기본값 {metrics['temperature']}이(가) 사용되었습니다.")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("생성 시간", f"{metrics['generation_time']:.2f}s")
                with col2:
                    st.metric("총 토큰", f"{metrics['total_tokens']:,}")
                with col3:
                    st.metric("예상 비용", f"${metrics['estimated_cost']:.4f}")
                with col4:
                    st.metric("프롬프트", metrics.get('prompt_style', 'original'))

            st.markdown("---")
            st.markdown("### 📋 주간 피드백")

            # V2/V3/public 스타일은 JSON 부분 제거하고 리포트만 표시
            if weekly_prompt_style in ["v2", "v3", "public", "v2_public"]:
                from llm_engineering.application.feedback.weekly.generator import WeeklyFeedbackGenerator
                display_feedback = WeeklyFeedbackGenerator.remove_json_section(feedback)
                st.markdown(display_feedback)
            else:
                st.markdown(feedback)
    else:
        st.info(f"""
        **🧪 주간 실험용 대시보드 - {provider}**

        7일간의 데이터를 분석하여 주간 피드백을 생성합니다:
        - 기간: {start_date} ~ {end_date}
        - 모델: {model_name}
        - 프롬프트 스타일: {style_label}
        - 과거 주간 리포트 참조 (최대 4개)

        **V2 스타일 특징:**
        - 사전 계산된 메트릭 사용 (LLM 연산 감소)
        - 패턴 분석에 집중
        - 이번 주 대표 태그 추출

        위 버튼을 클릭하여 주간 피드백을 생성하세요.
        """)


def main():
    st.title("🧪 활동 리포트 (실험용)")
    st.markdown("---")

    # 사이드바 설정 (모든 탭 공통)
    with st.sidebar:
        st.header("⚙️ 실험 설정")

        st.markdown("---")

        # Provider 선택
        st.subheader("🌐 Provider 선택")
        provider = st.radio(
            "LLM Provider",
            options=["OpenAI", "Gemini"],
            index=0,
            help="모델 제공자를 선택하세요"
        )

        # 선택한 Provider에 따라 모델 목록 변경
        if provider == "OpenAI":
            available_models = OPENAI_MODELS
            default_index = list(OPENAI_MODELS.keys()).index("gpt-4o-mini") if "gpt-4o-mini" in OPENAI_MODELS else 0
        else:
            available_models = GEMINI_MODELS
            default_index = list(GEMINI_MODELS.keys()).index("gemini-2.5-flash") if "gemini-2.5-flash" in GEMINI_MODELS else 0

        st.markdown("---")

        # 모델 선택
        st.subheader("🤖 모델 선택")
        model_id = st.selectbox(
            "LLM 모델",
            options=list(available_models.keys()),
            format_func=lambda x: available_models[x]["name"],
            index=default_index
        )

        # Temperature 설정
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help="높을수록 더 창의적이지만 일관성이 떨어짐"
        )

        # Temperature 제한 모델 경고
        if provider == "OpenAI":
            temperature_restricted = [
                "gpt-5", "gpt-5.1", "gpt-5-pro", "gpt-5-mini", "gpt-5-nano",
                "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"
            ]
            if model_id in temperature_restricted:
                st.caption("⚠️ 이 모델은 temperature 조정을 지원하지 않습니다. 기본값(1.0)이 사용됩니다.")

        st.markdown("---")

        # 프롬프트 스타일 선택
        st.subheader("📝 프롬프트 스타일")

        # 일별
        prompt_style = st.selectbox(
            "일별",
            options=PROMPT_STYLES,
            index=0
        )

        # 주간
        weekly_prompt_style = st.selectbox(
            "주간",
            options=["original", "v2", "v3", "public", "v2_public"],
            format_func=lambda x: {
                "original": "Original",
                "v2": "V2 (사전계산)",
                "v3": "V3 (2단계 체인)",
                "public": "Public (개인정보 보호)",
                "v2_public": "V2 Public (사전계산 + 개인정보 보호)"
            }[x],
            index=0
        )

        # 월간
        monthly_prompt_style = st.selectbox(
            "월간",
            options=["original", "v2_weekly_based", "public", "v2_public"],
            format_func=lambda x: {
                "original": "Original (계층적)",
                "v2_weekly_based": "V2 (주간 V2 기반)",
                "public": "Public (개인정보 보호)",
                "v2_public": "V2 Public (주간 V2 기반 + 개인정보 보호)"
            }[x],
            index=0
        )

        st.markdown("---")

        # 프라이버시 필터 토글
        st.subheader("🔒 프라이버시")
        apply_privacy = st.toggle(
            "필터 적용",
            value=False,
            help="켜면 인간관계 관련 메모가 마스킹됩니다"
        )

    # 메인 영역: 탭으로 분리
    tab_daily, tab_weekly, tab_monthly = st.tabs(["📅 일별 리포트", "📊 주간 리포트", "📈 월간 리포트"])

    # ===== 일별 리포트 탭 =====
    with tab_daily:
        # 날짜 선택
        col_date, col_btn = st.columns([3, 1])
        with col_date:
            selected_date = st.date_input(
                "분석할 날짜",
                value=datetime.now().date(),
                key="daily_date"
            )
        with col_btn:
            st.write("")  # 간격 조정
            if st.button("📥 로드", type="primary", key="daily_load", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        date_str = selected_date.strftime("%Y-%m-%d")

        # 데이터 로드
        with st.spinner("데이터 로딩 중..."):
            df = load_daily_data(date_str, apply_privacy_filter=apply_privacy)

        if df is None:
            st.error(f"⚠️  {date_str}에 해당하는 데이터가 없습니다.")
            st.info("다른 날짜를 선택해주세요.")
            return

        weekday = get_weekday_korean(date_str)
        st.success(f"✅ {date_str} ({weekday}) 데이터 로드 완료 (총 {len(df)}개 활동)")

        # 2-Column Layout
        left_col, right_col = st.columns([2, 1])

        with left_col:
            show_statistics(df, date_str)
            st.markdown("---")
            show_agency_pie_chart(df)
            st.markdown("---")
            show_category_distribution(df)
            st.markdown("---")
            show_sleep_breakdown(df)
            st.markdown("---")
            show_five_areas_analysis(df)

        with right_col:
            st.header("🧪 LLM 피드백")
            show_llm_feedback_experiment(date_str, provider, model_id, temperature, prompt_style)

    # ===== 주간 리포트 탭 =====
    with tab_weekly:
        # 날짜 선택
        today = datetime.now().date()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)

        col_start, col_end, col_btn = st.columns([2, 2, 1])
        with col_start:
            start_date = st.date_input(
                "시작일 (월요일)",
                value=last_monday,
                key="weekly_start"
            )
        with col_end:
            end_date = st.date_input(
                "종료일 (일요일)",
                value=last_sunday,
                key="weekly_end"
            )
        with col_btn:
            st.write("")  # 간격 조정
            if st.button("📥 로드", type="primary", key="weekly_load", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # 데이터 로드
        with st.spinner(f"주간 데이터 로딩 중... ({start_date_str} ~ {end_date_str})"):
            df = load_weekly_data(start_date_str, end_date_str, apply_privacy_filter=apply_privacy)

        if df is None:
            st.error(f"⚠️  {start_date_str} ~ {end_date_str} 기간에 해당하는 데이터가 없습니다.")
            st.info("다른 날짜를 선택해주세요.")
            return

        st.success(f"✅ 주간 데이터 로드 완료: {start_date_str} ~ {end_date_str} (총 {len(df)}개 활동)")

        # 2-Column Layout: 왼쪽(시각화/통계), 오른쪽(LLM 피드백)
        left_col, right_col = st.columns([2, 1])

        with left_col:
            # 1. 주간 통계
            show_statistics(df, start_date_str, is_weekly=True, start_date=start_date_str, end_date=end_date_str)

            st.markdown("---")

            # 2. Agency 파이차트
            show_agency_pie_chart(df)

            st.markdown("---")

            # 3. 카테고리별 분포
            show_category_distribution(df)

            st.markdown("---")

            # 4. 일별 요약 (주간 전용)
            st.subheader("📅 일별 요약")
            if 'ref_date' in df.columns:
                daily_summary = df.groupby('ref_date').agg({
                    'duration_minutes': 'sum',
                    'original_id': 'count',
                    'has_relationship_tag': 'sum',
                    'is_risky_recharger': 'sum'
                }).rename(columns={
                    'duration_minutes': '총 시간(분)',
                    'original_id': '활동 수',
                    'has_relationship_tag': '#인간관계',
                    'is_risky_recharger': '#즉시만족'
                })
                daily_summary['총 시간'] = daily_summary['총 시간(분)'].apply(format_duration)
                st.dataframe(
                    daily_summary[['총 시간', '활동 수', '#인간관계', '#즉시만족']],
                    use_container_width=True
                )
            else:
                st.info("일별 요약을 표시할 수 없습니다.")

            st.markdown("---")
            st.info("💡 주간 시각화는 추후 업데이트 예정입니다. 현재는 기본 통계만 제공됩니다.")

        with right_col:
            st.header("🧪 LLM 피드백")
            show_weekly_llm_feedback_experiment(
                start_date_str, end_date_str, provider, model_id, temperature,
                weekly_prompt_style=weekly_prompt_style,
                df=df
            )

    # ===== 월간 리포트 탭 =====
    with tab_monthly:
        # 날짜 선택
        today = datetime.now().date()

        col_year, col_month, col_btn = st.columns([2, 2, 1])
        with col_year:
            year = st.number_input(
                "연도",
                min_value=2020,
                max_value=2030,
                value=today.year,
                step=1,
                key="monthly_year"
            )
        with col_month:
            month = st.number_input(
                "월",
                min_value=1,
                max_value=12,
                value=today.month,
                step=1,
                key="monthly_month"
            )
        with col_btn:
            st.write("")  # 간격 조정
            if st.button("📥 로드", type="primary", key="monthly_load", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        # 데이터 로드
        with st.spinner(f"월간 데이터 로딩 중... ({year}년 {month}월)"):
            df = load_monthly_data(year, month, apply_privacy_filter=apply_privacy)

        if df is None:
            st.error(f"⚠️  {year}년 {month}월에 해당하는 데이터가 없습니다.")
            st.info("다른 날짜를 선택해주세요.")
            return

        st.success(f"✅ 월간 데이터 로드 완료: {year}년 {month}월 (총 {len(df)}개 활동)")

        # 2-Column Layout
        left_col, right_col = st.columns([2, 1])

        with left_col:
            st.subheader(f"📊 {year}년 {month}월 전체 통계")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("총 기록 시간", format_duration(df['duration_minutes'].sum()))
            with col2:
                st.metric("총 활동 수", f"{len(df)}개")
            with col3:
                st.metric("#인간관계", f"{df['has_relationship_tag'].sum()}개")
            with col4:
                st.metric("#즉시만족", f"{df['is_risky_recharger'].sum()}개")

            st.markdown("---")
            show_agency_pie_chart(df)
            st.markdown("---")
            show_category_distribution(df)
            st.markdown("---")

            st.subheader("📅 주별 요약")
            if 'ref_date' in df.columns:
                df_copy = df.copy()
                df_copy['week'] = pd.to_datetime(df_copy['ref_date']).dt.isocalendar().week
                weekly_summary = df_copy.groupby('week').agg({
                    'duration_minutes': 'sum',
                    'original_id': 'count',
                    'has_relationship_tag': 'sum',
                    'is_risky_recharger': 'sum'
                }).rename(columns={
                    'duration_minutes': '총 시간(분)',
                    'original_id': '활동 수',
                    'has_relationship_tag': '#인간관계',
                    'is_risky_recharger': '#즉시만족'
                })
                weekly_summary['총 시간'] = weekly_summary['총 시간(분)'].apply(format_duration)
                st.dataframe(
                    weekly_summary[['총 시간', '활동 수', '#인간관계', '#즉시만족']],
                    use_container_width=True
                )
            else:
                st.info("주별 요약을 표시할 수 없습니다.")

        with right_col:
            st.header("🧪 LLM 피드백")
            show_monthly_llm_feedback_experiment(
                year, month, provider, model_id, temperature,
                monthly_prompt_style=monthly_prompt_style,
                df=df
            )


if __name__ == "__main__":
    main()
