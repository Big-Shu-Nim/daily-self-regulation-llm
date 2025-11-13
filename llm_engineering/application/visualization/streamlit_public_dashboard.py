"""
일별 활동 리포트 - 공개 배포용 대시보드

개인정보 보호 정책:
- 최근 7일 데이터만 표시
- 일/생산, 학습/성장 카테고리의 메모만 공개
- #인간관계 관련 상세 내용 비공개
- LLM 피드백은 공개용 프롬프트 사용

왼쪽: Interactive 시각화 인사이트
오른쪽: 공개용 LLM 피드백
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

from llm_engineering.domain.cleaned_documents import CleanedCalendarDocument
from llm_engineering.domain.feedback_documents import PublicDailyFeedbackDocument
from llm_engineering.application.feedback.daily.generator import DailyFeedbackGenerator
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
PUBLIC_START_DATE = datetime(2025, 11, 5).date()
PUBLIC_END_DATE = datetime(2025, 11, 12).date()


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


def show_statistics(df: pd.DataFrame, target_date: str):
    """전체 통계 표시"""
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
            temperature=0.7,
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
    """공개용 일일 피드백 영역 (public 프롬프트 고정)"""
    st.caption("개인정보 보호를 위해 일반화된 분석을 제공합니다.")

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
            **🌐 피드백범위 **

        - ⚖️ 4가지 모드(생산, 학습, 유지, 회복) 기반 시간 균형 분석
        - 🌙 루틴 붕괴 원인 진단
        - 📉 충동적 에너지 소모 패턴  식별
        - 🚨 데이터 기반 대응 제안 

        **프라이버시 보호**:
        - 개인 식별 정보 제외
        - 민감한 메모 내용 비공개 
        - 인간관계 상세 내용 비공개

        위 버튼을 클릭하여 피드백을 확인하세요.
        """)

        # 자동 로드 옵션
        if st.checkbox("페이지 로드 시 자동으로 피드백 불러오기"):
            feedback, is_new = load_or_generate_feedback(date_str)
            st.markdown("---")
            st.markdown("### 📋 공개용 일일 피드백")
            st.markdown(feedback)


def main():
    st.title("📊 일별 활동 리포트")
    st.markdown("---")

    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 설정")

        # 공개용 날짜 범위 안내
        st.info(f"""
        **📅 공개 데이터 범위**

        {PUBLIC_START_DATE.strftime('%Y-%m-%d')} ~ {PUBLIC_END_DATE.strftime('%Y-%m-%d')}

        샘플 데이터 기간입니다.
        """)

        # 날짜 선택 (공개 범위로 제한)
        default_date = PUBLIC_END_DATE  # 가장 최근 날짜를 기본값으로
        selected_date = st.date_input(
            "분석할 날짜",
            value=default_date,
            min_value=PUBLIC_START_DATE,
            max_value=PUBLIC_END_DATE
        )

        date_str = selected_date.strftime("%Y-%m-%d")

        # 데이터 로드 버튼
        if st.button("📥 데이터 로드", type="primary"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("### 📌 사용 가이드")
        st.markdown("""
        1. 📅 날짜를 선택하세요
        2. 📥 데이터 로드 버튼을 클릭하세요
      
        """)
   
        st.markdown("""

        """)

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


if __name__ == "__main__":
    main()
