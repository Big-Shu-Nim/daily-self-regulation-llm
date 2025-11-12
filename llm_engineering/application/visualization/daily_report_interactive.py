"""
Interactive 시각화 모듈 (Plotly 기반)

호버 시 메모를 보여주는 interactive 시각화 함수들을 제공합니다.
"""

import pandas as pd
import plotly.graph_objects as go
from typing import Optional


def format_duration(minutes: float) -> str:
    """분을 'X시간 Y분' 포맷으로 변환"""
    hours = int(minutes // 60)
    mins = int(minutes % 60)

    if hours > 0 and mins > 0:
        return f"{hours}시간 {mins}분"
    elif hours > 0:
        return f"{hours}시간"
    else:
        return f"{mins}분"


def plot_work_by_event_interactive(
    df: pd.DataFrame,
    height: int = 600
) -> Optional[go.Figure]:
    """
    일/생산 이벤트별 시간 (Interactive, 호버 시 메모 표시)

    Args:
        df: 활동 데이터프레임
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    work_df = df[df['category_name'] == '일 / 생산'].copy()

    if len(work_df) == 0:
        return None

    # 시작 시간 기준 정렬 (0-24시 순서)
    work_df = work_df.sort_values('start_datetime').reset_index(drop=True)

    # Y축 레이블 생성
    y_labels = [
        f"{row['start_datetime'].strftime('%H:%M')} | {row['event_name'][:40]}"
        for _, row in work_df.iterrows()
    ]

    # Hover text 생성 (메모 포함)
    hover_texts = []
    for _, row in work_df.iterrows():
        hover_parts = [
            f"<b>{row['event_name']}</b>",
            f"시작: {row['start_datetime'].strftime('%H:%M')}",
            f"종료: {row['end_datetime'].strftime('%H:%M')}",
            f"소요: {format_duration(row['duration_minutes'])}",
        ]

        # 메모가 있으면 추가
        if row.get('notes') and str(row['notes']).strip():
            notes = str(row['notes']).strip()
            # 메모가 길면 줄바꿈
            if len(notes) > 60:
                notes = '<br>'.join([notes[i:i+60] for i in range(0, len(notes), 60)])
            hover_parts.append(f"<br>메모: {notes}")

        hover_texts.append('<br>'.join(hover_parts))

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=work_df['duration_minutes'].values,
        y=y_labels,
        orientation='h',
        marker=dict(color='#D58258', line=dict(color='black', width=1)),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 agency 스타일)
    fig.update_layout(
        title=dict(
            text=f'일/생산 - 이벤트별 집중 시간 ({len(work_df)}개)',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=10, color='white'),
            side='left'
        ),
        height=max(400, len(work_df) * 30),
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    return fig


def plot_learning_by_event_interactive(
    df: pd.DataFrame,
    height: int = 600
) -> Optional[go.Figure]:
    """
    학습/성장 이벤트별 시간 (Interactive, 호버 시 메모 표시)

    Args:
        df: 활동 데이터프레임
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    learning_df = df[df['category_name'] == '학습 / 성장'].copy()

    if len(learning_df) == 0:
        return None

    # 시작 시간 기준 정렬 (0-24시 순서)
    learning_df = learning_df.sort_values('start_datetime').reset_index(drop=True)

    # Y축 레이블 생성
    y_labels = [
        f"{row['start_datetime'].strftime('%H:%M')} | {row['event_name'][:40]}"
        for _, row in learning_df.iterrows()
    ]

    # Hover text 생성 (메모 포함)
    hover_texts = []
    for _, row in learning_df.iterrows():
        hover_parts = [
            f"<b>{row['event_name']}</b>",
            f"시작: {row['start_datetime'].strftime('%H:%M')}",
            f"종료: {row['end_datetime'].strftime('%H:%M')}",
            f"소요: {format_duration(row['duration_minutes'])}",
        ]

        # 학습 메타데이터
        if row.get('learning_method'):
            hover_parts.append(f"방법: {row['learning_method']}")
        if row.get('learning_target'):
            hover_parts.append(f"대상: {row['learning_target']}")

        # 메모가 있으면 추가
        if row.get('notes') and str(row['notes']).strip():
            notes = str(row['notes']).strip()
            if len(notes) > 60:
                notes = '<br>'.join([notes[i:i+60] for i in range(0, len(notes), 60)])
            hover_parts.append(f"<br>메모: {notes}")

        hover_texts.append('<br>'.join(hover_parts))

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=learning_df['duration_minutes'].values,
        y=y_labels,
        orientation='h',
        marker=dict(color='#3E6D94', line=dict(color='black', width=1)),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 agency 스타일)
    fig.update_layout(
        title=dict(
            text=f'학습/성장 - 이벤트별 집중 시간 ({len(learning_df)}개)',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=10, color='white'),
            side='left'
        ),
        height=max(400, len(learning_df) * 30),
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    return fig


def plot_recharge_by_event_interactive(
    df: pd.DataFrame,
    top_n: int = 15,
    height: int = 600
) -> Optional[go.Figure]:
    """
    재충전 활동 이벤트별 시간 (Interactive, 호버 시 메모 표시)
    재충전: 휴식/회복 + 운동 + 수면
    #인간관계가 있으면 "소셜 재충전"으로 구분

    Args:
        df: 활동 데이터프레임
        top_n: 상위 N개 이벤트 표시
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    recharge_categories = ['휴식 / 회복', '운동', '수면']
    recharge_df = df[df['category_name'].isin(recharge_categories)].copy()

    if len(recharge_df) == 0:
        return None

    # 이벤트별 총 시간 기준 상위 N개 선택
    event_duration = recharge_df.groupby('event_name')['duration_minutes'].sum().sort_values(ascending=False).head(top_n)

    # 선택된 이벤트만 필터링
    recharge_df = recharge_df[recharge_df['event_name'].isin(event_duration.index)].copy()

    # 시작 시간 기준 정렬 (0-24시 순서)
    recharge_df = recharge_df.sort_values('start_datetime').reset_index(drop=True)

    # Y축 레이블 생성
    y_labels = [
        f"{row['start_datetime'].strftime('%H:%M')} | {row['event_name'][:40]}"
        for _, row in recharge_df.iterrows()
    ]

    # Hover text 생성 (메모 포함)
    hover_texts = []
    colors = []

    for _, row in recharge_df.iterrows():
        hover_parts = [
            f"<b>{row['event_name']}</b>",
            f"카테고리: {row['category_name']}",
            f"시작: {row['start_datetime'].strftime('%H:%M')}",
            f"종료: {row['end_datetime'].strftime('%H:%M')}",
            f"소요: {format_duration(row['duration_minutes'])}",
        ]

        # 태그 정보
        tags = []
        if row.get('has_relationship_tag'):
            tags.append('#인간관계 (소셜)')
        if row.get('is_risky_recharger'):
            tags.append('#즉시만족')

        if tags:
            hover_parts.append(f"태그: {' '.join(tags)}")

        # 메모가 있으면 추가
        if row.get('notes') and str(row['notes']).strip():
            notes = str(row['notes']).strip()
            if len(notes) > 60:
                notes = '<br>'.join([notes[i:i+60] for i in range(0, len(notes), 60)])
            hover_parts.append(f"<br>메모: {notes}")

        hover_texts.append('<br>'.join(hover_parts))

        # 색상: #인간관계면 진한 녹색(소셜), 아니면 기본 녹색
        if row.get('has_relationship_tag'):
            colors.append('#456558')  # 소셜 재충전 (진한 녹색)
        else:
            colors.append('#6A8E7F')  # 전체 재충전 (기본 녹색)

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=recharge_df['duration_minutes'].values,
        y=y_labels,
        orientation='h',
        marker=dict(color=colors, line=dict(color='black', width=1)),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 agency 스타일)
    fig.update_layout(
        title=dict(
            text=f'재충전 활동 - 이벤트별 시간 (TOP {len(recharge_df)}개)',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=10, color='white'),
            side='left'
        ),
        height=max(400, len(recharge_df) * 30),
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    return fig


def plot_drain_by_event_interactive(
    df: pd.DataFrame,
    height: int = 600
) -> Optional[go.Figure]:
    """
    Drain 이벤트별 시간 (Interactive, 호버 시 메모 표시)

    Args:
        df: 활동 데이터프레임
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    drain_df = df[df['category_name'] == 'Drain'].copy()

    if len(drain_df) == 0:
        return None

    # 시작 시간 기준 정렬 (0-24시 순서)
    drain_df = drain_df.sort_values('start_datetime').reset_index(drop=True)

    # Y축 레이블 생성
    y_labels = [
        f"{row['start_datetime'].strftime('%H:%M')} | {row['event_name'][:40]}"
        for _, row in drain_df.iterrows()
    ]

    # Hover text 생성 (메모 포함)
    hover_texts = []
    for _, row in drain_df.iterrows():
        hover_parts = [
            f"<b>{row['event_name']}</b>",
            f"시작: {row['start_datetime'].strftime('%H:%M')}",
            f"종료: {row['end_datetime'].strftime('%H:%M')}",
            f"소요: {format_duration(row['duration_minutes'])}",
        ]

        # 메모가 있으면 추가
        if row.get('notes') and str(row['notes']).strip():
            notes = str(row['notes']).strip()
            if len(notes) > 60:
                notes = '<br>'.join([notes[i:i+60] for i in range(0, len(notes), 60)])
            hover_parts.append(f"<br>메모: {notes}")

        hover_texts.append('<br>'.join(hover_parts))

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=drain_df['duration_minutes'].values,
        y=y_labels,
        orientation='h',
        marker=dict(color='darkred', line=dict(color='black', width=1)),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 agency 스타일)
    fig.update_layout(
        title=dict(
            text=f'Drain - 이벤트별 시간 ({len(drain_df)}개)',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=10, color='white'),
            side='left'
        ),
        height=max(400, len(drain_df) * 30),
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    return fig


def plot_maintenance_by_event_interactive(
    df: pd.DataFrame,
    top_n: int = 15,
    height: int = 600
) -> Optional[go.Figure]:
    """
    일상 관리 이벤트별 시간 (Interactive, 호버 시 메모 표시)
    일상 관리: 유지/정리 + Daily/Chore
    #인간관계가 있으면 "소셜 활동"으로 구분

    Args:
        df: 활동 데이터프레임
        top_n: 상위 N개 이벤트 표시
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    maintenance_categories = ['유지 / 정리', 'Daily / Chore']
    maintenance_df = df[df['category_name'].isin(maintenance_categories)].copy()

    if len(maintenance_df) == 0:
        return None

    # 이벤트별 총 시간 기준 상위 N개 선택
    event_duration = maintenance_df.groupby('event_name')['duration_minutes'].sum().sort_values(ascending=False).head(top_n)

    # 선택된 이벤트만 필터링
    maintenance_df = maintenance_df[maintenance_df['event_name'].isin(event_duration.index)].copy()

    # 시작 시간 기준 정렬 (0-24시 순서)
    maintenance_df = maintenance_df.sort_values('start_datetime').reset_index(drop=True)

    # Y축 레이블 생성
    y_labels = [
        f"{row['start_datetime'].strftime('%H:%M')} | {row['event_name'][:40]}"
        for _, row in maintenance_df.iterrows()
    ]

    # Hover text 생성 (메모 포함)
    hover_texts = []
    colors = []

    for _, row in maintenance_df.iterrows():
        hover_parts = [
            f"<b>{row['event_name']}</b>",
            f"카테고리: {row['category_name']}",
            f"시작: {row['start_datetime'].strftime('%H:%M')}",
            f"종료: {row['end_datetime'].strftime('%H:%M')}",
            f"소요: {format_duration(row['duration_minutes'])}",
        ]

        # 태그 정보
        if row.get('has_relationship_tag'):
            hover_parts.append(f"태그: #인간관계 (소셜)")

        # 메모가 있으면 추가
        if row.get('notes') and str(row['notes']).strip():
            notes = str(row['notes']).strip()
            if len(notes) > 60:
                notes = '<br>'.join([notes[i:i+60] for i in range(0, len(notes), 60)])
            hover_parts.append(f"<br>메모: {notes}")

        hover_texts.append('<br>'.join(hover_parts))

        # 색상: #인간관계면 진한 브라운(소셜), 아니면 기본 브라운
        if row.get('has_relationship_tag'):
            colors.append('#6D554C')  # 소셜 활동 (진한 브라운)
        else:
            colors.append('#8D6E63')  # 일상 관리 (기본 브라운)

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=maintenance_df['duration_minutes'].values,
        y=y_labels,
        orientation='h',
        marker=dict(color=colors, line=dict(color='black', width=1)),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 agency 스타일)
    fig.update_layout(
        title=dict(
            text=f'일상 관리 - 이벤트별 시간 (TOP {len(maintenance_df)}개)',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=10, color='white'),
            side='left'
        ),
        height=max(400, len(maintenance_df) * 30),
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    return fig


def plot_relationship_by_agency_interactive(
    df: pd.DataFrame,
    height: int = 600
) -> Optional[go.Figure]:
    """
    #인간관계 태그가 있는 활동들을 Agency별로 분류 (Interactive, 호버 시 메모 표시)

    Args:
        df: 활동 데이터프레임
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    # #인간관계 태그가 있는 이벤트만 필터링
    relationship_df = df[df['has_relationship_tag'] == True].copy()

    if len(relationship_df) == 0:
        return None

    # 카테고리를 Agency로 매핑
    category_to_agency_map = {
        '수면': '휴식 / 회복',
        '휴식 / 회복': '휴식 / 회복',
        '운동': '휴식 / 회복',
        'Drain': 'Drain',
        '학습 / 성장': '학습 / 성장',
        '일 / 생산': '일 / 생산',
        '유지 / 정리': '유지 / 정리',
        'Daily / Chore': '유지 / 정리'
    }

    agency_colors = {
        '일 / 생산': '#D58258',
        '학습 / 성장': '#3E6D94',
        '유지 / 정리': '#8D6E63',
        '휴식 / 회복': '#6A8E7F',
        'Drain': 'darkred'
    }

    relationship_df['agency_name'] = relationship_df['category_name'].map(category_to_agency_map)
    relationship_df = relationship_df[relationship_df['agency_name'].notna()].copy()

    if len(relationship_df) == 0:
        return None

    # Agency별 시간 집계
    agency_duration = relationship_df.groupby('agency_name')['duration_minutes'].sum().sort_values(ascending=True)

    # Y축 레이블
    y_labels = list(agency_duration.index)

    # 색상 매핑
    colors = [agency_colors.get(agency, 'lightgray') for agency in agency_duration.index]

    # Hover text 생성
    hover_texts = []
    for agency, total_mins in agency_duration.items():
        # 해당 agency의 이벤트 수 계산
        event_count = len(relationship_df[relationship_df['agency_name'] == agency])

        hover_parts = [
            f"<b>{agency} (#인간관계)</b>",
            f"총 시간: {format_duration(total_mins)}",
            f"활동 수: {event_count}개",
        ]

        # 대표 이벤트 3개 표시
        agency_events = relationship_df[relationship_df['agency_name'] == agency].sort_values(
            'duration_minutes', ascending=False
        ).head(3)

        if len(agency_events) > 0:
            hover_parts.append("<br>주요 이벤트:")
            for _, event in agency_events.iterrows():
                event_line = f"  • {event['event_name'][:30]} ({format_duration(event['duration_minutes'])})"
                hover_parts.append(event_line)

        hover_texts.append('<br>'.join(hover_parts))

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=agency_duration.values,
        y=y_labels,
        orientation='h',
        marker=dict(color=colors, line=dict(color='black', width=1)),
        text=[format_duration(mins) for mins in agency_duration.values],
        textposition='auto',
        textfont=dict(color='white', size=11),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 agency 스타일)
    fig.update_layout(
        title=dict(
            text='#인간관계 태그 - Agency별 시간 분포',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=11, color='white'),
            side='left'
        ),
        height=max(350, len(agency_duration) * 80),
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        margin=dict(l=150, r=50, t=80, b=50),
    )

    return fig


def plot_agency_pie_chart_interactive(
    df: pd.DataFrame,
    height: int = 600
) -> Optional[go.Figure]:
    """
    Agency 기반 파이 차트 (Interactive, 호버 시 실제 시간 표시)

    Args:
        df: 활동 데이터프레임
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    if df.empty:
        return None

    category_to_agency_map = {
        '수면': '휴식 / 회복',
        '휴식 / 회복': '휴식 / 회복',
        '운동': '휴식 / 회복',
        'Drain': 'Drain',
        '학습 / 성장': '학습 / 성장',
        '일 / 생산': '일 / 생산',
        '유지 / 정리': '유지 / 정리',
        'Daily / Chore': '유지 / 정리'
    }

    agency_colors = {
        '일 / 생산': '#D58258',
        '학습 / 성장': '#3E6D94',
        '유지 / 정리': '#8D6E63',
        '휴식 / 회복': '#6A8E7F',
        'Drain': 'darkred'
    }

    df_agency = df.copy()
    df_agency['agency_name'] = df_agency['category_name'].map(category_to_agency_map)
    df_agency['agency_name'] = df_agency['agency_name'].fillna('기타')

    agency_duration = df_agency.groupby('agency_name')['duration_minutes'].sum()
    agency_duration = agency_duration[agency_duration > 0]

    if agency_duration.empty:
        return None

    # 색상 매핑
    colors = [agency_colors.get(name, 'lightgray') for name in agency_duration.index]

    # pull 값 (Drain 강조)
    pull_values = [0.1 if label == 'Drain' else 0 for label in agency_duration.index]

    # Hover text 생성 (실제 시간 표시)
    hover_texts = [
        f"<b>{name}</b><br>시간: {format_duration(mins)}<br>비율: {mins/agency_duration.sum()*100:.1f}%"
        for name, mins in zip(agency_duration.index, agency_duration.values)
    ]

    # Figure 생성
    fig = go.Figure(data=[go.Pie(
        labels=agency_duration.index,
        values=agency_duration.values,
        hole=0.3,
        marker=dict(colors=colors, line=dict(color='white', width=2)),
        pull=pull_values,
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
        textinfo='label+percent',
        textfont=dict(size=12, color='white'),
    )])

    # Layout 설정 (v5 agency 스타일)
    fig.update_layout(
        title=dict(
            text='주요 활동 영역별 시간 분포 (Agency)',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        height=height,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        showlegend=True,
        legend=dict(
            font=dict(color='white')
        )
    )

    return fig


def plot_category_distribution_interactive(
    df: pd.DataFrame,
    height: int = 600
) -> Optional[go.Figure]:
    """
    카테고리별 시간 분포 (Interactive, 하루 기준 퍼센티지 표시)

    Args:
        df: 활동 데이터프레임
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    category_duration = df.groupby('category_name')['duration_minutes'].sum().sort_values(ascending=True)

    if category_duration.empty:
        return None

    total_minutes = df['duration_minutes'].sum()

    # 조건부 색상 설정 (v5 스타일)
    colors = []
    for category, minutes in category_duration.items():
        is_warning = (
            (category == '휴식 / 회복' and minutes > 180) or
            (category == '유지 / 정리' and minutes > 180) or
            (category == '수면' and minutes < 360) or
            (category == 'Drain' and minutes > 180)
        )
        colors.append('darkred' if is_warning else 'darkgray')

    # 퍼센티지 계산
    percentages = [(mins / total_minutes * 100) for mins in category_duration.values]

    # Y축 레이블 (퍼센티지 없이)
    y_labels = list(category_duration.index)

    # Hover text 생성 (퍼센티지 표시)
    hover_texts = [
        f"<b>{cat}</b><br>시간: {format_duration(mins)}<br>비율: {pct:.1f}%"
        for cat, mins, pct in zip(category_duration.index, category_duration.values, percentages)
    ]

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=category_duration.values,
        y=y_labels,
        orientation='h',
        marker=dict(color=colors, line=dict(color='black', width=1)),
        text=[format_duration(mins) for mins in category_duration.values],
        textposition='auto',
        textfont=dict(color='white', size=10),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 스타일)
    fig.update_layout(
        title=dict(
            text='카테고리별 시간 분포',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=11, color='white'),
            side='left'
        ),
        height=max(400, len(category_duration) * 50),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        showlegend=False,
        margin=dict(l=150, r=50, t=80, b=50),
    )

    return fig


def plot_sleep_breakdown_interactive(
    df: pd.DataFrame,
    height: int = 500
) -> Optional[go.Figure]:
    """
    수면 상세 분석 (Interactive, 호버 시 메모 표시)

    Args:
        df: 활동 데이터프레임
        height: 그래프 높이

    Returns:
        plotly Figure 객체 (데이터 없으면 None)
    """
    sleep_df = df[df['category_name'] == '수면'].copy()

    if len(sleep_df) == 0:
        return None

    # 시각화를 위한 전처리
    def classify_sleep(event_name: str) -> str:
        if not event_name:
            return '기타'
        event_lower = event_name.lower()
        if '수면시도' in event_lower or '불면증' in event_lower or '수면 시도' in event_lower:
            return '수면시도/불면증'
        if '쪽잠' in event_lower or '낮잠' in event_lower:
            return '쪽잠/낮잠'
        if '수면' in event_lower:
            return '수면'
        return '기타'

    sleep_df['sleep_type'] = sleep_df['event_name'].apply(classify_sleep)

    # 유형별로 이벤트 정보 수집
    sleep_events = []
    for sleep_type in sleep_df['sleep_type'].unique():
        type_df = sleep_df[sleep_df['sleep_type'] == sleep_type].sort_values('start_datetime')
        for _, row in type_df.iterrows():
            sleep_events.append({
                'sleep_type': sleep_type,
                'event_name': row['event_name'],
                'duration_minutes': row['duration_minutes'],
                'start_time': row['start_datetime'].strftime('%H:%M'),
                'end_time': row['end_datetime'].strftime('%H:%M'),
                'notes': row.get('notes', '')
            })

    # Y축: 유형별 이벤트
    y_labels = []
    durations = []
    colors = []
    hover_texts = []

    colors_map = {'수면시도/불면증': 'darkred', '수면': 'darkgray', '쪽잠/낮잠': 'darkgray', '기타': 'darkgray'}

    for event in sleep_events:
        y_labels.append(f"{event['start_time']} | {event['event_name'][:30]}")
        durations.append(event['duration_minutes'])
        colors.append(colors_map.get(event['sleep_type'], 'darkgray'))

        # Hover text (메모 포함)
        hover_parts = [
            f"<b>{event['event_name']}</b>",
            f"유형: {event['sleep_type']}",
            f"시작: {event['start_time']}",
            f"종료: {event['end_time']}",
            f"소요: {format_duration(event['duration_minutes'])}",
        ]

        # 메모가 있으면 추가
        if event['notes'] and str(event['notes']).strip():
            notes = str(event['notes']).strip()
            if len(notes) > 60:
                notes = '<br>'.join([notes[i:i+60] for i in range(0, len(notes), 60)])
            hover_parts.append(f"<br>메모: {notes}")

        hover_texts.append('<br>'.join(hover_parts))

    # Figure 생성
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=durations,
        y=y_labels,
        orientation='h',
        marker=dict(color=colors, line=dict(color='black', width=1)),
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
    ))

    # Layout 설정 (v5 스타일)
    fig.update_layout(
        title=dict(
            text='수면 상세 분석',
            font=dict(size=16, color='white', family='NanumGothic, sans-serif')
        ),
        xaxis=dict(visible=False),  # X축 숨김
        yaxis=dict(
            tickfont=dict(size=10, color='white'),
            side='left'
        ),
        height=max(400, len(sleep_events) * 40),
        hovermode='closest',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='NanumGothic, sans-serif'),
        margin=dict(l=50, r=50, t=80, b=50),
    )

    return fig
