"""
상일별/주간/월간 활동 리포트 - 공개 배포용 대시보드

개인정보 보호 정책:
- 최근 7일 데이터만 표시
- 일/생산, 학습/성장 카테고리의 메모만 공개
- #인간관계 관련 상세 내용 비공개
- LLM 피드백은 공개용 프롬프트 사용 (v2_public)
- 주간/월간 리포트는 사전 계산 메트릭 기반 V2 Public 스타일 사용

LLM 모델: GPT-5 (OpenAI 최신 모델)

탭 구조:
- 일일: Interactive 시각화 + 공개용 일일 피드백
- 주간: V2 Public (사전계산 메트릭 + 개인정보 보호)
- 월간: V2 Public (주간 V2 기반 + 개인정보 보호)
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger

from llm_engineering.domain.cleaned_documents import CleanedCalendarDocument
from llm_engineering.domain.feedback_documents import (
    PublicDailyFeedbackDocument,
    PublicWeeklyFeedbackDocument,
    PublicMonthlyFeedbackDocument,
)
from llm_engineering.application.feedback.daily.generator import DailyFeedbackGenerator
from llm_engineering.application.feedback.weekly.generator import WeeklyFeedbackGenerator
from llm_engineering.application.feedback.weekly.metrics import compute_weekly_metrics
from llm_engineering.application.feedback.document_loader import DocumentLoader
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
    validate_public_data,
    get_public_summary_stats,
)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


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


# 공개용 대시보드 날짜 범위 제한 (샘플 기간)
PUBLIC_START_DATE = datetime(2025, 11, 3).date()
PUBLIC_END_DATE = datetime(2025, 11, 27).date()


# 페이지 설정
st.set_page_config(
    page_title="일별 활동 리포트 (공개)",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_daily_data(date_str: str) -> pd.DataFrame:
    """
    특정 날짜의 CleanedCalendarDocument를 로드하여 DataFrame으로 변환.
    공개 배포용: 프라이버시 필터 자동 적용
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

        # ✅ 공개 배포용 프라이버시 필터 적용
        df_filtered = apply_public_privacy_filter(
            df,
            days=7,
            ref_date=date_str,
            mask_notes=True,
            anonymize_names=True
        )

        return df_filtered
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {str(e)}")
        return None


def show_statistics(df: pd.DataFrame, target_date: str, is_weekly: bool = False, start_date: str = None, end_date: str = None):
    """전체 통계 표시 (일일/주간 모드 지원)"""
    if is_weekly and start_date and end_date:
        st.subheader(f"📊 주간 통계: {start_date} ~ {end_date}")
    else:
        weekday = get_weekday_korean(target_date)
        st.subheader(f"📊 {target_date} ({weekday}) 전체 통계")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # duration_minutes 컬럼 체크
        if 'duration_minutes' in df.columns:
            st.metric("총 기록 시간", format_duration(df['duration_minutes'].sum()))
        elif 'duration_hours' in df.columns:
            total_hours = df['duration_hours'].sum()
            st.metric("총 기록 시간", f"{total_hours:.1f}h")
        elif 'duration' in df.columns:
            st.metric("총 기록 시간", format_duration(df['duration'].sum()))
        else:
            st.metric("총 기록 시간", "N/A")

    with col2:
        st.metric("총 활동 수", f"{len(df)}개")

    with col3:
        # 공개용이므로 인간관계/즉시만족 메트릭은 조건부 표시
        if 'has_relationship_tag' in df.columns:
            st.metric("#인간관계", f"{df['has_relationship_tag'].sum()}개")
        elif 'duration_minutes' in df.columns:
            avg_duration = df['duration_minutes'].mean()
            st.metric("평균 활동 시간", format_duration(avg_duration) if not pd.isna(avg_duration) else "N/A")
        else:
            st.metric("평균 활동 시간", "N/A")

    with col4:
        if 'is_risky_recharger' in df.columns:
            st.metric("#즉시만족", f"{df['is_risky_recharger'].sum()}개")
        elif 'category' in df.columns:
            st.metric("활동 유형", f"{df['category'].nunique()}개")
        else:
            st.metric("활동 유형", "N/A")


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




def load_or_generate_feedback(date_str: str) -> tuple[str, bool]:
    """
    공개용 일일 피드백을 로드하거나 생성합니다.

    공개용 대시보드 전용 함수:
    - prompt_style: "public" 고정
    - 별도 컬렉션(public_daily_feedback) 사용
    - 개인용 피드백과 완전 분리

    Args:
        date_str: 날짜 (YYYY-MM-DD)

    Returns:
        (피드백 내용, 새로 생성 여부)
    """
    # 1. 공개용 컬렉션에서 기존 피드백 확인
    existing_feedback = PublicDailyFeedbackDocument.find(
        target_date=date_str
    )

    if existing_feedback:
        return existing_feedback.content, False

    # 2. 새로 생성 (public 프롬프트 사용)
    try:
        generator = DailyFeedbackGenerator(
            model_id="gpt-5",  # GPT-5를 기본 모델로 사용
            temperature=1.0,  # GPT-5는 기본값(1.0)만 지원
            prompt_style="public"  # 공개용 프롬프트 고정
        )

        # 피드백 생성 (개인용 DB에 저장하지 않음)
        feedback_content = generator.generate(
            target_date=date_str,
            include_previous=True,
            include_next=True,
            save_to_db=False  # 개인용 DB에 저장 안 함
        )

        # 3. 공개용 컬렉션에 저장
        public_feedback = PublicDailyFeedbackDocument(
            target_date=date_str,
            content=feedback_content,
            model_used=generator.model_id,  # model_id가 올바른 속성명
            temperature=generator.temperature,
            prompt_style="public",
            include_previous=True,
            include_next=True,
        )
        public_feedback.save()

        return feedback_content, True
    except Exception as e:
        return f"❌ 피드백 생성 중 오류 발생: {str(e)}", False


def show_llm_feedback(date_str: str):
    """공개용 일일 피드백 영역 (GPT-5, public 프롬프트 고정)"""
    st.caption("🤖 Powered by GPT-5 | 개인정보 보호를 위해 일반화된 분석을 제공합니다.")

    # 피드백 생성/로드 버튼
    col1, col2 = st.columns([1, 1])

    with col1:
        load_button = st.button("📥 피드백 불러오기", type="primary", use_container_width=True)

    with col2:
        regenerate_button = st.button("🔄 새로 생성", use_container_width=True)

    st.markdown("---")

    # 피드백 표시 영역
    if load_button or regenerate_button:
        with st.spinner("피드백 로딩 중..." if load_button else "피드백 생성 중..."):
            if regenerate_button:
                # 강제 재생성: 기존 공개용 피드백 삭제 후 생성
                try:
                    existing = PublicDailyFeedbackDocument.find(
                        target_date=date_str
                    )
                    if existing:
                        # MongoDB에서 삭제하는 메서드가 있다면 사용
                        pass  # 일단 덮어쓰기로 처리
                except:
                    pass

            feedback, is_new = load_or_generate_feedback(date_str)

            if is_new:
                st.success("✅ 새로운 피드백이 생성되었습니다!")
            else:
                st.info("📥 저장된 피드백을 불러왔습니다.")

            st.markdown("---")
            st.markdown("### 📋 일일 피드백")
            st.markdown(feedback)
    else:
        # 초기 상태 또는 자동 로드
        st.info("""
            **🌐 GPT-5 기반 일일 피드백**

        **분석 범위**:
        - ⚖️ 4가지 모드(생산, 학습, 유지, 회복) 기반 시간 균형 분석
        - 🌙 루틴 붕괴 원인 진단
        - 📉 충동적 에너지 소모 패턴 식별
        - 🚨 데이터 기반 대응 제안

        **프라이버시 보호**:
        - 개인 식별 정보 제외
        - 민감한 메모 내용 비공개
        - 인간관계 상세 내용 비공개

        **모델**: GPT-5 (OpenAI 최신 모델)

        위 버튼을 클릭하여 피드백을 확인하세요.
        """)

        # 자동 로드 옵션
        if st.checkbox("페이지 로드 시 자동으로 피드백 불러오기"):
            feedback, is_new = load_or_generate_feedback(date_str)
            st.markdown("---")
            st.markdown("### 📋 공개용 일일 피드백")
            st.markdown(feedback)


# ============================================================================
# 주간/월간 V2 Public 생성 헬퍼 함수들
# ============================================================================

async def _generate_weekly_v2_report_async(
    week_num: int,
    week_start: str,
    week_end: str,
    week_df: pd.DataFrame,
    model_id: str,
    temperature: float,
) -> str:
    """
    단일 주간 V2 Public 리포트를 비동기로 생성합니다.

    Args:
        week_num: 주 번호
        week_start: 주 시작 날짜
        week_end: 주 종료 날짜
        week_df: 해당 주의 데이터 DataFrame
        model_id: 모델 ID
        temperature: 온도

    Returns:
        주간 V2 Public 리포트 문자열 (JSON 제거됨)
    """
    if week_df.empty:
        return f"### Week {week_num}: {week_start} ~ {week_end}\n\n데이터 없음\n\n---"

    logger.info(f"Generating v2_public report for Week {week_num}: {week_start} ~ {week_end}")

    # 주간 메트릭 계산
    week_metrics = compute_weekly_metrics(week_df, week_start, week_end)

    # 주간 V2 Public 리포트 생성
    generator = WeeklyFeedbackGenerator(
        model_id=model_id,
        temperature=temperature,
        prompt_style="v2_public",  # 항상 v2_public 사용
    )

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

    logger.info(f"Week {week_num} v2_public report generated ({len(week_feedback_clean)} chars)")

    return f"### Week {week_num}: {week_start} ~ {week_end}\n\n{week_feedback_clean}\n\n---"


async def _generate_all_weekly_v2_reports_async(
    weeks: list[tuple[str, str]],
    df: pd.DataFrame,
    model_id: str,
    temperature: float,
) -> list[str]:
    """
    모든 주간 V2 Public 리포트를 병렬로 생성합니다.

    Args:
        weeks: [(week_start, week_end), ...] 리스트
        df: 월간 데이터 DataFrame
        model_id: 모델 ID
        temperature: 온도

    Returns:
        주간 V2 Public 리포트 리스트
    """
    tasks = []
    for week_num, (week_start, week_end) in enumerate(weeks, 1):
        # 해당 주의 데이터 필터링
        week_df = df[
            (df['ref_date'] >= week_start) &
            (df['ref_date'] <= week_end)
        ].copy()

        task = _generate_weekly_v2_report_async(
            week_num, week_start, week_end, week_df, model_id, temperature
        )
        tasks.append(task)

    logger.info(f"Starting parallel generation of {len(tasks)} weekly v2_public reports")
    reports = await asyncio.gather(*tasks)
    logger.info(f"Completed parallel generation of {len(reports)} weekly v2_public reports")

    return reports


def _generate_monthly_from_weekly_v2(
    year: int,
    month: int,
    model_id: str,
    temperature: float,
    df: pd.DataFrame,
) -> str:
    """
    주간 V2 Public 리포트를 병렬로 생성한 후 이를 기반으로 월간 V2 Public 요약을 생성합니다.

    Args:
        year: 연도
        month: 월
        model_id: 모델 ID
        temperature: 온도
        df: 월간 데이터 DataFrame

    Returns:
        월간 V2 Public 피드백 문자열
    """
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

    # 2. 각 주별 V2 Public 리포트 병렬 생성
    weekly_v2_reports = asyncio.run(
        _generate_all_weekly_v2_reports_async(weeks, df, model_id, temperature)
    )

    # 3. 주간 V2 Public 리포트들을 종합하여 월간 피드백 생성
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


def load_or_generate_weekly_feedback(
    start_date: str,
    end_date: str,
    df: pd.DataFrame
) -> tuple[str, bool, dict]:
    """
    공개용 주간 피드백을 로드하거나 생성합니다.

    Args:
        start_date: 주 시작일 (YYYY-MM-DD)
        end_date: 주 종료일 (YYYY-MM-DD)
        df: 주간 데이터 DataFrame

    Returns:
        (피드백 내용, 새로 생성 여부, 메트릭)
    """
    # 1. 공개용 컬렉션에서 기존 피드백 확인
    existing_feedback = PublicWeeklyFeedbackDocument.find(
        target_date=start_date,
        end_date=end_date
    )

    if existing_feedback:
        metrics = existing_feedback.precomputed_metrics or {}
        return existing_feedback.content, False, metrics

    # 2. 새로 생성 (v2_public 프롬프트 사용)
    try:
        # 주간 메트릭 계산
        metrics = compute_weekly_metrics(df, start_date, end_date)

        # V2 Public 주간 리포트 생성
        generator = WeeklyFeedbackGenerator(
            model_id="gpt-5",
            temperature=1.0,  # GPT-5는 temperature=1.0만 지원
            prompt_style="v2_public"
        )

        feedback = generator.generate(
            start_date=start_date,
            end_date=end_date,
            precomputed_metrics=metrics,
        )

        # JSON 제거
        feedback_clean = WeeklyFeedbackGenerator.remove_json_section(feedback)

        # 3. 공개용 컬렉션에 저장
        public_feedback = PublicWeeklyFeedbackDocument(
            target_date=start_date,
            end_date=end_date,
            content=feedback_clean,
            model_used=generator.model_id,
            temperature=generator.temperature,
            prompt_style="v2_public",
            precomputed_metrics=metrics,
        )
        public_feedback.save()

        return feedback_clean, True, metrics
    except Exception as e:
        logger.error(f"Weekly feedback generation error: {e}", exc_info=True)
        return f"❌ 피드백 생성 중 오류 발생: {str(e)}", False, {}


def load_or_generate_monthly_feedback(
    year: int,
    month: int,
    df: pd.DataFrame
) -> tuple[str, bool]:
    """
    공개용 월간 피드백을 로드하거나 생성합니다.

    Args:
        year: 연도
        month: 월
        df: 월간 데이터 DataFrame

    Returns:
        (피드백 내용, 새로 생성 여부)
    """
    # 1. 공개용 컬렉션에서 기존 피드백 확인
    existing_feedback = PublicMonthlyFeedbackDocument.find(
        year=year,
        month=month
    )

    if existing_feedback:
        return existing_feedback.content, False

    # 2. 새로 생성 (v2_public 프롬프트 사용)
    try:
        # V2 Public 월간 리포트 생성
        feedback = _generate_monthly_from_weekly_v2(
            year=year,
            month=month,
            model_id="gpt-5",
            temperature=1.0,  # GPT-5는 temperature=1.0만 지원
            df=df,
        )

        # 3. 공개용 컬렉션에 저장
        public_feedback = PublicMonthlyFeedbackDocument(
            target_date=f"{year}-{month:02d}",
            year=year,
            month=month,
            content=feedback,
            model_used="gpt-5",
            temperature=1.0,
            prompt_style="v2_public",
        )
        public_feedback.save()

        return feedback, True
    except Exception as e:
        logger.error(f"Monthly feedback generation error: {e}", exc_info=True)
        return f"❌ 피드백 생성 중 오류 발생: {str(e)}", False


def load_weekly_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    주간 데이터 로드.

    Note: 개인정보 보호는 V2 Public 프롬프트에서 처리하므로
    별도의 privacy 필터를 적용하지 않습니다.
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

        # metadata에서 필드 추출
        data = []
        for doc in all_docs:
            metadata = doc.metadata
            data.append({
                'original_id': str(doc.original_id),
                'ref_date': doc.ref_date,
                'start_datetime': pd.to_datetime(metadata.get('start_datetime')),
                'end_datetime': pd.to_datetime(metadata.get('end_datetime')),
                'duration_minutes': metadata.get('duration_minutes', 0),
                'category': metadata.get('category_name'),
                'category_name': metadata.get('category_name'),
                'calendar_name': metadata.get('category_name'),
                'event_name': metadata.get('event_name'),
                'notes': metadata.get('notes', ''),
                'sub_category': metadata.get('sub_category', ''),
                'learning_method': metadata.get('learning_method'),
                'learning_target': metadata.get('learning_target'),
                'work_tags': metadata.get('work_tags', []),
                'exercise_type': metadata.get('exercise_type'),
                'agency_mode': metadata.get('agency_mode'),
                'is_risky_recharger': metadata.get('is_risky_recharger', False),
                'has_relationship_tag': metadata.get('has_relationship_tag', False),
                'has_emotion_event': metadata.get('has_emotion_event', False),
            })

        df = pd.DataFrame(data)
        df = df.sort_values('start_datetime').reset_index(drop=True)

        return df
    except Exception as e:
        st.error(f"주간 데이터 로드 중 오류 발생: {str(e)}")
        return None


def load_monthly_data(year: int, month: int) -> pd.DataFrame:
    """월간 데이터 로드"""
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

        # metadata에서 필드 추출
        data = []
        for doc in all_docs:
            metadata = doc.metadata
            data.append({
                'original_id': str(doc.original_id),
                'ref_date': doc.ref_date,
                'start_datetime': pd.to_datetime(metadata.get('start_datetime')),
                'end_datetime': pd.to_datetime(metadata.get('end_datetime')),
                'duration_minutes': metadata.get('duration_minutes', 0),
                'category': metadata.get('category_name'),
                'category_name': metadata.get('category_name'),
                'calendar_name': metadata.get('category_name'),
                'event_name': metadata.get('event_name'),
                'notes': metadata.get('notes', ''),
                'sub_category': metadata.get('sub_category', ''),
                'learning_method': metadata.get('learning_method'),
                'learning_target': metadata.get('learning_target'),
                'work_tags': metadata.get('work_tags', []),
                'exercise_type': metadata.get('exercise_type'),
                'agency_mode': metadata.get('agency_mode'),
                'is_risky_recharger': metadata.get('is_risky_recharger', False),
                'has_relationship_tag': metadata.get('has_relationship_tag', False),
                'has_emotion_event': metadata.get('has_emotion_event', False),
            })

        df = pd.DataFrame(data)
        df = df.sort_values('start_datetime').reset_index(drop=True)

        return df
    except Exception as e:
        st.error(f"월간 데이터 로드 중 오류 발생: {str(e)}")
        return None


def main():
    # 탭 생성 
    tab_daily, tab_weekly, tab_monthly = st.tabs(["📅 일일", "📈 주간", "📊 월간"])

    # 사이드바 공통 정보
    with st.sidebar:
      
        st.markdown("---")
        st.header("ℹ️ 공통 정보")

        # 공개용 날짜 범위 안내
        st.info(f"""
        **📅 공개 데이터 범위**

        {PUBLIC_START_DATE.strftime('%Y-%m-%d')} ~ {PUBLIC_END_DATE.strftime('%Y-%m-%d')}

        데모 적용 기간입니다.
        """)

        st.info("""
        **🤖 LLM 모델**

        GPT-5 (OpenAI 최신 모델)
        """)

    # ========================================================================
    # 탭 1: 일일 리포트
    # ========================================================================
    with tab_daily:
        st.header("📅 일일 활동 리포트")
        st.markdown("---")

        # 날짜 선택 (탭 내부)
        col1, col2 = st.columns([3, 1])
        with col1:
            default_date = PUBLIC_END_DATE
            selected_date = st.date_input(
                "📅 분석할 날짜",
                value=default_date,
                min_value=PUBLIC_START_DATE,
                max_value=PUBLIC_END_DATE,
                key="daily_date"
            )
            date_str = selected_date.strftime("%Y-%m-%d")

        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📥 데이터 로드", type="primary", key="daily_load"):
                st.cache_data.clear()
                st.rerun()

        # 데이터 로드
        with st.spinner("데이터 로딩 중..."):
            df = load_daily_data(date_str)

        if df is None:
            st.error(f"⚠️  {date_str}에 해당하는 데이터가 없습니다.")
            st.info("다른 날짜를 선택해주세요.")
            return

        weekday = get_weekday_korean(date_str)
        st.success(f"✅ {date_str} ({weekday}) 데이터 로드 완료 (총 {len(df)}개 활동)")

        # 2-Column Layout: 왼쪽(시각화), 오른쪽(LLM 피드백)
        left_col, right_col = st.columns([2, 1])

        with left_col:

            # 1. 전체 통계
            show_statistics(df, date_str)

            st.markdown("---")

            # 2. Agency 파이차트
            show_agency_pie_chart(df)

            st.markdown("---")

            # 3. 카테고리별 분포
            show_category_distribution(df)

            st.markdown("---")

            # 4. 수면 분석
            show_sleep_breakdown(df)

            st.markdown("---")

            # 5. 5개 영역 상세 분석 (Interactive)
            show_five_areas_analysis(df)

        with right_col:
            st.header("🌐 공개 배포용 LLM 피드백")

            # 일일 피드백 영역
            show_llm_feedback(date_str)

    # ========================================================================
    # 탭 2: 주간 리포트 (V2 Public)
    # ========================================================================
    with tab_weekly:
        st.header("📈 주간 활동 리포트")
        st.markdown("---")
        # 날짜 선택
        col_start, col_end, col_btn = st.columns([2, 2, 1])
        with col_start:
            start_date = st.date_input(
                "시작일",
                value=PUBLIC_START_DATE,
                min_value=PUBLIC_START_DATE,
                max_value=PUBLIC_END_DATE,
                key="weekly_start"
            )
        with col_end:
            end_date = st.date_input(
                "종료일",
                value=min(start_date + timedelta(days=6), PUBLIC_END_DATE),
                min_value=start_date,
                max_value=PUBLIC_END_DATE,
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
            df = load_weekly_data(start_date_str, end_date_str)

        if df is None or df.empty:
            st.error(f"⚠️ {start_date_str} ~ {end_date_str} 기간에 해당하는 데이터가 없습니다.")
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
                agg_dict = {'original_id': 'count'} if 'original_id' in df.columns else {}

                # duration 컬럼 찾기
                if 'duration_minutes' in df.columns:
                    agg_dict['duration_minutes'] = 'sum'
                    duration_col = 'duration_minutes'
                elif 'duration_hours' in df.columns:
                    agg_dict['duration_hours'] = 'sum'
                    duration_col = 'duration_hours'
                elif 'duration' in df.columns:
                    agg_dict['duration'] = 'sum'
                    duration_col = 'duration'
                else:
                    duration_col = None

                if agg_dict:
                    daily_summary = df.groupby('ref_date').agg(agg_dict)

                    if duration_col:
                        if duration_col == 'duration_minutes' or duration_col == 'duration':
                            daily_summary['총 시간'] = daily_summary[duration_col].apply(format_duration)
                        else:  # duration_hours
                            daily_summary['총 시간'] = daily_summary[duration_col].apply(lambda x: f"{x:.1f}h")

                    if 'original_id' in daily_summary.columns:
                        daily_summary = daily_summary.rename(columns={'original_id': '활동 수'})

                    display_cols = []
                    if '총 시간' in daily_summary.columns:
                        display_cols.append('총 시간')
                    if '활동 수' in daily_summary.columns:
                        display_cols.append('활동 수')

                    if display_cols:
                        st.dataframe(daily_summary[display_cols], use_container_width=True)
                    else:
                        st.info("일별 요약을 표시할 수 없습니다.")
                else:
                    st.info("일별 요약을 표시할 수 없습니다.")
            else:
                st.info("일별 요약을 표시할 수 없습니다.")

        with right_col:
            st.header("🌐 공개용 LLM 피드백")
            st.caption("🤖 Powered by GPT-5 | V2 Public | 개인정보 보호를 위해 일반화된 분석을 제공합니다.")

            # 피드백 생성/로드 버튼
            col1, col2 = st.columns([1, 1])

            with col1:
                load_button = st.button("📥 피드백 불러오기", type="primary", use_container_width=True, key="weekly_load_btn")

            with col2:
                regenerate_button = st.button("🔄 새로 생성", use_container_width=True, key="weekly_regenerate_btn")

            st.markdown("---")

            # 피드백 표시 영역
            if load_button or regenerate_button:
                with st.spinner("피드백 로딩 중..." if load_button else "피드백 생성 중..."):
                    if regenerate_button:
                        # 강제 재생성: 기존 공개용 피드백 삭제 후 생성
                        try:
                            existing = PublicWeeklyFeedbackDocument.find(
                                target_date=start_date_str,
                                end_date=end_date_str
                            )
                            if existing:
                                pass  # 일단 덮어쓰기로 처리
                        except:
                            pass

                    feedback, is_new, metrics = load_or_generate_weekly_feedback(
                        start_date_str, end_date_str, df
                    )

                    if is_new:
                        st.success("✅ 새로운 피드백이 생성되었습니다!")
                    else:
                        st.info("📥 저장된 피드백을 불러왔습니다.")

                    # 메트릭 미리보기
                    if metrics:
                        with st.expander("📊 메트릭 미리보기"):
                            st.json(metrics)

                    st.markdown("---")
                    st.markdown("### 📋 주간 피드백")
                    st.markdown(feedback)
            else:
                # 초기 상태
                st.info("""
                    **🌐 GPT-5 기반 주간 피드백 (V2 Public)**

                **분석 범위**:
                - 📊 사전 계산된 메트릭 기반 분석
                - 🎯 Agency 모드별 시간 배분 및 패턴
                - 🔄 Drain/Recovery 비율 분석
                - 📈 주간 대표 태그 5-7개 추출

                **프라이버시 보호**:
                - 개인 식별 정보 제외
                - 민감한 메모 내용 비공개
                - 인간관계 상세 내용 비공개

                **모델**: GPT-5 (OpenAI 최신 모델)

                위 버튼을 클릭하여 피드백을 확인하세요.
                """)

                # 자동 로드 옵션
                if st.checkbox("페이지 로드 시 자동으로 피드백 불러오기", key="weekly_auto_load"):
                    feedback, is_new, metrics = load_or_generate_weekly_feedback(
                        start_date_str, end_date_str, df
                    )
                    if metrics:
                        with st.expander("📊 메트릭 미리보기"):
                            st.json(metrics)
                    st.markdown("---")
                    st.markdown("### 📋 주간 피드백")
                    st.markdown(feedback)

    # ========================================================================
    # 탭 3: 월간 리포트 (V2 Public)
    # ========================================================================
    with tab_monthly:
        st.header("📊 월간 활동 리포트")
        st.markdown("---")
        # 날짜 선택 (샘플 기간으로 제한)
        current_year = PUBLIC_END_DATE.year
        current_month = PUBLIC_END_DATE.month

        # 샘플 기간의 연도/월 범위 계산
        min_year = PUBLIC_START_DATE.year
        max_year = PUBLIC_END_DATE.year
        min_month = PUBLIC_START_DATE.month if min_year == max_year else 1
        max_month = PUBLIC_END_DATE.month if min_year == max_year else 12

        col_year, col_month, col_btn = st.columns([2, 2, 1])
        with col_year:
            year = st.number_input(
                "연도",
                min_value=min_year,
                max_value=max_year,
                value=current_year,
                step=1,
                key="monthly_year"
            )
        with col_month:
            month = st.number_input(
                "월",
                min_value=min_month,
                max_value=max_month,
                value=current_month,
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
            df = load_monthly_data(year, month)

        if df is None or df.empty:
            st.error(f"⚠️ {year}년 {month}월에 해당하는 데이터가 없습니다.")
            st.info("다른 날짜를 선택해주세요.")
            return

        st.success(f"✅ 월간 데이터 로드 완료: {year}년 {month}월 (총 {len(df)}개 활동)")

        # 2-Column Layout: 왼쪽(시각화/통계), 오른쪽(LLM 피드백)
        left_col, right_col = st.columns([2, 1])

        with left_col:
            st.subheader(f"📊 {year}년 {month}월 전체 통계")

            col1, col2 = st.columns(2)
            with col1:
                # duration_minutes 컬럼 체크
                if 'duration_minutes' in df.columns:
                    st.metric("총 기록 시간", format_duration(df['duration_minutes'].sum()))
                elif 'duration_hours' in df.columns:
                    st.metric("총 기록 시간", f"{df['duration_hours'].sum():.1f}h")
                elif 'duration' in df.columns:
                    st.metric("총 기록 시간", format_duration(df['duration'].sum()))
                else:
                    st.metric("총 기록 시간", "N/A")
            with col2:
                st.metric("총 활동 수", f"{len(df)}개")

            st.markdown("---")

            # Agency 파이차트
            show_agency_pie_chart(df)

            st.markdown("---")

            # 카테고리별 분포
            show_category_distribution(df)

            st.markdown("---")

            # 주별 요약
            st.subheader("📅 주별 요약")
            if 'ref_date' in df.columns:
                df_copy = df.copy()
                df_copy['week'] = pd.to_datetime(df_copy['ref_date']).dt.isocalendar().week

                agg_dict = {'original_id': 'count'} if 'original_id' in df_copy.columns else {}

                # duration 컬럼 찾기
                if 'duration_minutes' in df_copy.columns:
                    agg_dict['duration_minutes'] = 'sum'
                    duration_col = 'duration_minutes'
                elif 'duration_hours' in df_copy.columns:
                    agg_dict['duration_hours'] = 'sum'
                    duration_col = 'duration_hours'
                elif 'duration' in df_copy.columns:
                    agg_dict['duration'] = 'sum'
                    duration_col = 'duration'
                else:
                    duration_col = None

                if agg_dict:
                    weekly_summary = df_copy.groupby('week').agg(agg_dict)

                    if duration_col:
                        if duration_col == 'duration_minutes' or duration_col == 'duration':
                            weekly_summary['총 시간'] = weekly_summary[duration_col].apply(format_duration)
                        else:  # duration_hours
                            weekly_summary['총 시간'] = weekly_summary[duration_col].apply(lambda x: f"{x:.1f}h")

                    if 'original_id' in weekly_summary.columns:
                        weekly_summary = weekly_summary.rename(columns={'original_id': '활동 수'})

                    display_cols = []
                    if '총 시간' in weekly_summary.columns:
                        display_cols.append('총 시간')
                    if '활동 수' in weekly_summary.columns:
                        display_cols.append('활동 수')

                    if display_cols:
                        st.dataframe(weekly_summary[display_cols], use_container_width=True)
                    else:
                        st.info("주별 요약을 표시할 수 없습니다.")
                else:
                    st.info("주별 요약을 표시할 수 없습니다.")
            else:
                st.info("주별 요약을 표시할 수 없습니다.")

        with right_col:
            st.header("🌐 공개용 LLM 피드백")
            st.caption("🤖 Powered by GPT-5 | V2 Public | 개인정보 보호를 위해 일반화된 분석을 제공합니다.")

            # 피드백 생성/로드 버튼
            col1, col2 = st.columns([1, 1])

            with col1:
                load_button = st.button("📥 피드백 불러오기", type="primary", use_container_width=True, key="monthly_load_btn")

            with col2:
                regenerate_button = st.button("🔄 새로 생성", use_container_width=True, key="monthly_regenerate_btn")

            st.markdown("---")

            # 피드백 표시 영역
            if load_button or regenerate_button:
                with st.spinner("피드백 로딩 중..." if load_button else "피드백 생성 중 (주간 리포트 병렬 생성 후 월간 요약)..."):
                    if regenerate_button:
                        # 강제 재생성: 기존 공개용 피드백 삭제 후 생성
                        try:
                            existing = PublicMonthlyFeedbackDocument.find(
                                year=year,
                                month=month
                            )
                            if existing:
                                pass  # 일단 덮어쓰기로 처리
                        except:
                            pass

                    feedback, is_new = load_or_generate_monthly_feedback(
                        year, month, df
                    )

                    if is_new:
                        st.success("✅ 새로운 피드백이 생성되었습니다!")
                    else:
                        st.info("📥 저장된 피드백을 불러왔습니다.")

                    st.markdown("---")
                    st.markdown("### 📋 월간 피드백")
                    st.markdown(feedback)
            else:
                # 초기 상태
                st.info("""
                    **🌐 GPT-5 기반 월간 피드백 (V2 Public)**

                **분석 범위**:
                - 📊 주간 V2 Public 리포트 기반 계층적 요약
                - 🔄 월간 트렌드 및 반복 패턴 분석
                - 🎯 장기적 성과 및 문제점 식별
                - 💡 다음 달 개선 전략 제시

                **프라이버시 보호**:
                - 개인 식별 정보 제외
                - 민감한 메모 내용 비공개
                - 인간관계 상세 내용 비공개

                **모델**: GPT-5 (OpenAI 최신 모델)

                위 버튼을 클릭하여 피드백을 확인하세요.
                """)

                # 자동 로드 옵션
                if st.checkbox("페이지 로드 시 자동으로 피드백 불러오기", key="monthly_auto_load"):
                    feedback, is_new = load_or_generate_monthly_feedback(
                        year, month, df
                    )
                    st.markdown("---")
                    st.markdown("### 📋 월간 피드백")
                    st.markdown(feedback)


if __name__ == "__main__":
    main()
