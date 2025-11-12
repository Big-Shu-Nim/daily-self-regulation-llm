"""
일별 활동 리포트 Streamlit 대시보드

왼쪽: Interactive 시각화 인사이트
오른쪽: LLM 피드백 (추후 구현)
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
from llm_engineering.domain.feedback_documents import DailyFeedbackDocument
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


# 페이지 설정
st.set_page_config(
    page_title="일별 활동 리포트",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_daily_data(date_str: str) -> pd.DataFrame:
    """특정 날짜의 CleanedCalendarDocument를 로드하여 DataFrame으로 변환"""
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
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {str(e)}")
        return None


def show_statistics(df: pd.DataFrame, target_date: str):
    """전체 통계 표시"""
    st.subheader(f"📊 {target_date} 전체 통계")

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
    st.subheader("🎯 Agency 파이차트")
    st.caption("💡 Tip: 호버하면 실제 영역별 합계 시간을 확인할 수 있습니다!")

    fig = plot_agency_pie_chart_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  Agency 데이터가 없습니다.")


def show_category_distribution(df: pd.DataFrame):
    """카테고리별 시간 분포 표시 (Interactive)"""
    st.subheader("📈 카테고리별 시간 분포")
    st.caption("💡 Tip: 바를 호버하면 하루 기준 퍼센티지를 확인할 수 있습니다!")

    fig = plot_category_distribution_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  카테고리 데이터가 없습니다.")


def show_sleep_breakdown(df: pd.DataFrame):
    """수면 상세 분석 표시 (Interactive)"""
    st.subheader("😴 수면 상세 분석")
    st.caption("💡 Tip: 바를 호버하면 각 수면 이벤트의 메모를 확인할 수 있습니다!")

    fig = plot_sleep_breakdown_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  수면 데이터가 없습니다.")


def show_five_areas_analysis(df: pd.DataFrame):
    """5개 영역 상세 분석 (Interactive Plotly)"""
    st.subheader("🎯 5개 영역 상세 분석")
    st.caption("💡 Tip: 바를 호버하면 메모와 상세 정보를 확인할 수 있습니다!")

    # 1. 일/생산
    st.markdown("### 💼 일/생산 - 이벤트별 집중 시간")
    fig = plot_work_by_event_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  일/생산 데이터가 없습니다.")

    st.markdown("---")

    # 2. 학습/성장
    st.markdown("### 📚 학습/성장 - 이벤트별 집중 시간")
    fig = plot_learning_by_event_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  학습/성장 데이터가 없습니다.")

    st.markdown("---")

    # 3. 재충전 활동
    st.markdown("### 🌴 재충전 활동 - 이벤트별")
    st.caption("🟩 기본 재충전 / 🟫 소셜 재충전 (#인간관계)")
    fig = plot_recharge_by_event_interactive(df, top_n=15)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  재충전 활동 데이터가 없습니다.")

    st.markdown("---")

    # 4. Drain
    st.markdown("### ⚠️ Drain - 이벤트별")
    fig = plot_drain_by_event_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  Drain 데이터가 없습니다.")

    st.markdown("---")

    # 5. 일상 관리
    st.markdown("### 🏠 일상 관리 - 이벤트별")
    fig = plot_maintenance_by_event_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  일상 관리 데이터가 없습니다.")

    st.markdown("---")

    # 6. #인간관계 태그 - Agency별
    st.markdown("### 👥 #인간관계 - Agency별 분포")
    fig = plot_relationship_by_agency_interactive(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️  #인간관계 태그 데이터가 없습니다.")




def load_or_generate_feedback(date_str: str, prompt_style: str = "dashboard") -> tuple[str, bool]:
    """
    일일 피드백을 로드하거나 생성합니다.

    Args:
        date_str: 날짜 (YYYY-MM-DD)
        prompt_style: 프롬프트 스타일

    Returns:
        (피드백 내용, 새로 생성 여부)
    """
    # 1. 기존 피드백 확인
    existing_feedback = DailyFeedbackDocument.find(
        target_date=date_str,
        prompt_style=prompt_style
    )

    if existing_feedback:
        return existing_feedback.content, False

    # 2. 새로 생성
    try:
        generator = DailyFeedbackGenerator(
            temperature=0.7,
            prompt_style=prompt_style
        )
        feedback = generator.generate(
            target_date=date_str,
            include_previous=True,
            include_next=True,
            save_to_db=True
        )
        return feedback, True
    except Exception as e:
        return f"❌ 피드백 생성 중 오류 발생: {str(e)}", False


def show_llm_feedback(date_str: str):
    """일일 피드백 영역"""
    st.markdown("### 설정")

    # 프롬프트 스타일 선택
    prompt_styles = {
        "dashboard": "📊 대시보드 (간결)",
        "original": "📝 오리지널 (상세)",
        "coach": "💪 코치 (동기부여)",
        "scientist": "🔬 과학자 (객관적)",
        "cbt": "🧠 CBT (인지행동)",
        "narrative": "📖 내러티브 (스토리)",
        "metacognitive": "🤔 메타인지 (성찰)"
    }

    selected_style = st.selectbox(
        "피드백 스타일",
        options=list(prompt_styles.keys()),
        format_func=lambda x: prompt_styles[x],
        index=0  # dashboard 기본
    )

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
                # 강제 재생성: 기존 피드백 삭제 후 생성
                try:
                    existing = DailyFeedbackDocument.find(
                        target_date=date_str,
                        prompt_style=selected_style
                    )
                    if existing:
                        # MongoDB에서 삭제하는 메서드가 있다면 사용
                        pass  # 일단 덮어쓰기로 처리
                except:
                    pass

            feedback, is_new = load_or_generate_feedback(date_str, selected_style)

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
        **🤖 AI 기반 일일 피드백**

        - 📝 일일 활동 요약 및 분석
        - 🎯 목표 대비 진행률
        - 💡 시간 사용 패턴 인사이트
        - 🔍 개선 제안사항

        위 버튼을 클릭하여 피드백을 확인하세요.
        """)

        # 자동 로드 옵션
        if st.checkbox("페이지 로드 시 자동으로 피드백 불러오기"):
            feedback, is_new = load_or_generate_feedback(date_str, selected_style)
            st.markdown("---")
            st.markdown("### 📋 일일 피드백")
            st.markdown(feedback)


def main():
    st.title("📊 일별 활동 리포트")
    st.markdown("---")

    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 설정")

        # 날짜 선택
        default_date = datetime.now() - timedelta(days=1)
        selected_date = st.date_input(
            "분석할 날짜",
            value=default_date,
            max_value=datetime.now()
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
        3. 💡 Interactive 차트에서 바를 호버하면 상세 정보를 볼 수 있습니다
        4. 📊 왼쪽: 시각화 인사이트
        5. 🤖 오른쪽: 일일 피드백 (개발 중)
        """)

    # 데이터 로드
    with st.spinner("데이터 로딩 중..."):
        df = load_daily_data(date_str)

    if df is None:
        st.error(f"⚠️  {date_str}에 해당하는 데이터가 없습니다.")
        st.info("다른 날짜를 선택해주세요.")
        return

    st.success(f"✅ {date_str} 데이터 로드 완료 (총 {len(df)}개 활동)")

    # 2-Column Layout: 왼쪽(시각화), 오른쪽(LLM 피드백)
    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.header("📊 시각화 인사이트")

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
        st.header("🤖 일일 피드백")

        # 일일 피드백 영역
        show_llm_feedback(date_str)


if __name__ == "__main__":
    main()
