"""
Calendar data preprocessor.

구조화된 캘린더 데이터를 자연어 형태로 변환하여 임베딩에 적합한 형태로 만듭니다.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any

import pandas as pd

from .base import BasePreprocessor
from .utils import parse_content_field


class CalendarPreprocessor(BasePreprocessor):
    """
    Calendar 데이터를 전처리하는 클래스.

    핵심 작업:
    1. content 필드 파싱 (event_name, notes 추출)
    2. 자정을 넘는 활동 분할
    3. ref_date 할당 (수면 활동은 종료 날짜 기준)
    4. 조건부 카테고리 이름 변경
    5. 태그 추출 및 정규화, Agency 모드 매핑, 행동 플래그 설정
    6. 구조화 데이터를 자연어로 변환 (임베딩용 content 생성)
    """

    # Sub Category 통합 규칙
    SUB_CATEGORY_NORMALIZATION_RULES = {
        # 휴식/회복 관련
        "휴식": "#휴식/회복",
        "회복": "#휴식/회복",
        "#휴식": "#휴식/회복",
        "#회복": "#휴식/회복",

        # 유지/정리 관련
        "유지": "#유지/정리",
        "정리": "#유지/정리",
        "#유지": "#유지/정리",
        "#정리": "#유지/정리",

        # 즉시만족 관련
        "즉시만족": "#즉시만족",
        "충동": "#즉시만족",
        "#충동": "#즉시만족",

        # 계획 관련
        "계획": "#계획",

        # 긴급 관련
        "긴급": "#긴급",
    }

    # ID 기반 아웃라이어 특수 처리: document_id → (new_sub_category, new_category)
    ID_BASED_FIXES = {
        "f2ab26f3-6bc5-42cb-8cd5-7848ef51bfc7": ("#휴식/회복", None),
        "db40fbdc-6004-4420-a726-2dcc00ee491d": ("#유지/정리", "인간관계"),
    }

    # Agency 모드 매핑: calendar_name → agency_mode
    AGENCY_MODE_RULES = {
        "Work/Production": [
            "일 / 생산", "프로젝트", "부업", "업무", "작업"
        ],
        "Learning/Growth": [
            "학습 / 성장", "스터디", "독서", "강의", "공부", "연습", "리서치"
        ],
        "Impulse/Distraction": [
            "충동루프", "충동 / 즉시만족", "즉시만족"
        ],
        "Rest/Recovery": [
            "수면", "운동", "휴식 / 회복", "휴식", "회복", "헬스", "유산소", "러닝"
        ],
        "Maintenance/Organization": [
            "daily/chore", "daily", "chore", "유지 / 정리", "유지",
            "식사", "샤워", "세면", "이동", "출퇴근"
        ]
    }

    # 이벤트 이름 단순 통일 규칙
    SIMPLE_NORMALIZATION = {
        # 유튜브 변형들
        "유튜브 보기": "유튜브",
        "유투브": "유튜브",
        "유튜브 시청": "유튜브",

        # 식사
        "아침식사": "식사",
        "점심식사": "식사",
        "저녁식사": "식사",
        "식사준비": "식사",
    }

    # 인식할 태그 (4가지만)
    RECOGNIZED_TAGS = ["#유지/정리", "#휴식/회복", "#감정이벤트", "#즉시만족"]

    def __init__(
        self,
        category_rename_rules: List[Dict[str, str]] = None,
        verbose: bool = True
    ):
        """
        Args:
            category_rename_rules: 카테고리 이름 변경 규칙 리스트
                예: [{"old": "개인개발", "new": "프로젝트", "before_date": "2024-06-01"}]
            verbose: 진행 상황 출력 여부
        """
        super().__init__(verbose)
        self.category_rename_rules = category_rename_rules or []

    def clean(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Calendar DataFrame을 전처리합니다.

        Args:
            df: 원본 Calendar DataFrame

        Returns:
            CleanedCalendarDocument에 맞는 dict 리스트
        """
        self.log("="*50)
        self.log(f"Calendar 전처리 시작: {len(df)}건")

        # 1. 필수 컬럼 검증
        required_columns = [
            'id', 'content', 'start_datetime', 'end_datetime',
            'calendar_name', 'author_id', 'author_full_name'
        ]
        self._validate_dataframe(df, required_columns)

        # 2. content 파싱
        df = self._parse_content(df)
        self.log("✅ content 필드 파싱 완료")

        # 3. Datetime 변환
        df['start_datetime'] = pd.to_datetime(df['start_datetime'])
        df['end_datetime'] = pd.to_datetime(df['end_datetime'])

        # 4. 자정 분할 및 ref_date 할당
        df = self._split_and_assign_ref_date(df)
        self.log(f"✅ 자정 분할 완료: {len(df)}건")

        # 5. 카테고리 이름 변경
        df = self._rename_categories(df)

        # 6. 태그 정규화 및 메타데이터 enrichment
        df = self._apply_tag_normalization(df)
        self.log("✅ 태그 정규화 및 메타데이터 enrichment 완료")

        # 7. 자연어 content 생성 및 cleaned document로 변환
        cleaned_documents = self._to_cleaned_documents(df)

        self.log(f"✅ Calendar 전처리 완료: {len(cleaned_documents)}건")
        self.log("="*50)

        return cleaned_documents

    def _parse_content(self, df: pd.DataFrame) -> pd.DataFrame:
        """content 필드를 파싱하여 event_name, notes 추출"""
        parsed = df["content"].map(parse_content_field)
        df["event_name"] = parsed.map(lambda d: d.get("title", ""))
        df["notes"] = parsed.map(lambda d: d.get("notes", ""))
        return df

    def _split_and_assign_ref_date(self, df: pd.DataFrame) -> pd.DataFrame:
        """자정을 넘는 활동을 분할하고 ref_date 할당"""
        processed_rows = []
        for _, row in df.iterrows():
            processed_rows.extend(self._split_row_across_midnight(row))

        df_processed = pd.DataFrame(processed_rows)
        df_processed['ref_date'] = pd.to_datetime(df_processed['ref_date']).dt.strftime('%Y-%m-%d')
        return df_processed

    def _split_row_across_midnight(self, row: pd.Series) -> List[Dict[str, Any]]:
        """
        활동을 00시 기준으로 분할하고 ref_date를 할당합니다.
        - 수면 활동: 종료 날짜를 ref_date로 하며 분할하지 않음
        - 기타 활동: 00시를 넘으면 분할
        """
        data = row.to_dict()
        start_dt = data['start_datetime']
        end_dt = data['end_datetime']
        is_sleep = "수면" in str(data.get("event_name", ""))

        # 수면 활동 처리
        if is_sleep:
            data['ref_date'] = end_dt.date()
            data['duration_minutes'] = (end_dt - start_dt).total_seconds() / 60
            return [data]

        # 같은 날짜면 분할 불필요
        if start_dt.date() == end_dt.date():
            data['ref_date'] = start_dt.date()
            data['duration_minutes'] = (end_dt - start_dt).total_seconds() / 60
            return [data]

        # 분할 필요
        result_rows = []
        current_dt = start_dt

        while current_dt < end_dt:
            next_midnight = pd.Timestamp(current_dt.date()) + pd.Timedelta(days=1)
            split_end_dt = min(end_dt, next_midnight)

            new_row = data.copy()
            new_row['start_datetime'] = current_dt
            new_row['end_datetime'] = split_end_dt
            new_row['ref_date'] = current_dt.date()
            new_row['duration_minutes'] = (split_end_dt - current_dt).total_seconds() / 60
            result_rows.append(new_row)

            current_dt = split_end_dt

        return result_rows

    def _rename_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """조건부 카테고리 이름 변경"""
        for rule in self.category_rename_rules:
            target_name = rule['old']
            new_name = rule['new']
            cutoff_date = rule['before_date']

            condition = (df['ref_date'] <= cutoff_date) & (df['calendar_name'] == target_name)
            count = condition.sum()
            df.loc[condition, 'calendar_name'] = new_name

            if count > 0:
                self.log(f"🔄 '{target_name}' → '{new_name}' 변경: {count}건 (기준일: {cutoff_date})")

        return df

    def _extract_tags_from_subcategory(self, sub_category: str) -> List[str]:
        """
        Sub Category에서 태그를 추출합니다.

        Args:
            sub_category: 서브 카테고리 문자열

        Returns:
            추출된 태그 리스트 (4가지 인식 태그만)
        """
        if not sub_category:
            return []

        tags = []
        for tag in self.RECOGNIZED_TAGS:
            if tag in sub_category:
                tags.append(tag)

        return tags

    def _clean_subcategory(
        self,
        sub_category: str,
        category: str,
        document_id: str
    ) -> tuple:
        """
        Sub Category를 정리합니다.

        우선순위:
        1. ID 기반 특수 처리 (최우선)
        2. 통합 규칙 적용
        3. 공백 제거 및 정리

        Args:
            sub_category: 원본 sub_category
            category: 카테고리 이름
            document_id: 문서 ID (ID 기반 수정용)

        Returns:
            (cleaned_sub_category, new_category)
        """
        # 1. ID 기반 특수 처리 (최우선)
        if document_id and document_id in self.ID_BASED_FIXES:
            new_sub, new_cat = self.ID_BASED_FIXES[document_id]
            return new_sub, new_cat

        # 2. None이거나 빈 문자열이면 그대로 반환
        if not sub_category or sub_category.strip() == "":
            return "", None

        # 3. 공백 제거
        cleaned = sub_category.strip()

        # 4. 통합 규칙 적용 (정확히 일치하는 경우)
        if cleaned in self.SUB_CATEGORY_NORMALIZATION_RULES:
            normalized = self.SUB_CATEGORY_NORMALIZATION_RULES[cleaned]
            return normalized, None

        # 5. 대소문자 무시하고 다시 시도
        cleaned_lower = cleaned.lower()
        for pattern, normalized in self.SUB_CATEGORY_NORMALIZATION_RULES.items():
            if pattern.lower() == cleaned_lower:
                return normalized, None

        # 6. 부분 매칭 (# 태그가 아닌 경우에만)
        if not cleaned.startswith("#"):
            for pattern, normalized in self.SUB_CATEGORY_NORMALIZATION_RULES.items():
                if pattern.lower() in cleaned_lower:
                    return normalized, None

        # 7. 규칙이 없으면 그대로 반환
        return cleaned, None

    def _map_agency_mode(self, category: str, sub_category: str) -> str:
        """
        Agency 모드를 매핑합니다.

        우선순위:
        1. sub_category 기준 매핑
        2. category 기준 매핑
        3. 기본값 → Maintenance/Organization

        Args:
            category: calendar_name
            sub_category: 서브 카테고리

        Returns:
            Agency 모드 (5가지 중 하나)
        """
        # 우선순위 1: sub_category 기준 매핑
        sub_lower = sub_category.lower()
        if "휴식" in sub_lower or "회복" in sub_lower:
            return "Rest/Recovery"
        if "유지" in sub_lower or "정리" in sub_lower:
            return "Maintenance/Organization"

        # 우선순위 2: category 기준 매핑
        category_lower = category.lower()
        for mode, keywords in self.AGENCY_MODE_RULES.items():
            for keyword in keywords:
                if keyword.lower() in category_lower:
                    return mode

        # 기본값
        return "Maintenance/Organization"

    def _normalize_title(self, title: str) -> str:
        """
        이벤트 이름을 정규화합니다.

        Args:
            title: 원본 이벤트 제목

        Returns:
            정규화된 제목
        """
        if not title:
            return ""

        # 단순 통일
        normalized_title = title
        for original, normalized in self.SIMPLE_NORMALIZATION.items():
            if original.lower() in normalized_title.lower():
                normalized_title = normalized_title.replace(original, normalized)

        return normalized_title

    def _apply_tag_normalization(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DataFrame에 태그 정규화, Agency 모드 매핑, 행동 플래그를 적용합니다.

        Args:
            df: 전처리 중인 Calendar DataFrame

        Returns:
            메타데이터가 enriched된 DataFrame
        """
        # 태그, agency_mode, 플래그를 저장할 컬럼 초기화
        df['extracted_tags'] = None
        df['agency_mode'] = None
        df['normalized_title'] = None
        df['is_risk_recharger'] = False
        df['is_emotional_event'] = False

        for idx, row in df.iterrows():
            document_id = str(row['id'])
            sub_category = row.get('sub_category', '') or ''
            category = row.get('calendar_name', '')
            title = row.get('event_name', '')

            # 1. 태그 추출
            extracted_tags = self._extract_tags_from_subcategory(sub_category)

            # 2. Sub category 정규화
            cleaned_sub_category, new_category = self._clean_subcategory(
                sub_category, category, document_id
            )

            # ID 기반 수정으로 카테고리가 변경된 경우
            if new_category:
                category = new_category
                df.at[idx, 'calendar_name'] = new_category

            # 3. Agency 모드 매핑
            agency_mode = self._map_agency_mode(category, cleaned_sub_category)

            # 4. 이벤트 제목 정규화
            normalized_title = self._normalize_title(title)

            # 5. 플래그 설정
            is_risk_recharger = "#즉시만족" in extracted_tags
            is_emotional_event = "#감정이벤트" in extracted_tags

            # DataFrame 업데이트
            df.at[idx, 'sub_category'] = cleaned_sub_category
            df.at[idx, 'extracted_tags'] = extracted_tags
            df.at[idx, 'agency_mode'] = agency_mode
            df.at[idx, 'normalized_title'] = normalized_title
            df.at[idx, 'is_risk_recharger'] = is_risk_recharger
            df.at[idx, 'is_emotional_event'] = is_emotional_event

        return df

    def _to_cleaned_documents(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        DataFrame을 CleanedCalendarDocument dict 리스트로 변환.
        구조화 데이터를 자연어 content로 변환하는 핵심 로직.
        """
        cleaned_docs = []

        for _, row in df.iterrows():
            # 자연어 content 생성
            content = self._synthesize_natural_language_content(row)

            # Metadata 구성 (기본 정보 + enriched 정보)
            metadata = {
                "start_datetime": row['start_datetime'].isoformat() if pd.notna(row['start_datetime']) else None,
                "end_datetime": row['end_datetime'].isoformat() if pd.notna(row['end_datetime']) else None,
                "duration_minutes": int(row['duration_minutes']) if pd.notna(row['duration_minutes']) else 0,
                "category_name": row.get('calendar_name', ''),
                "event_name": row.get('event_name', ''),
                "notes": row.get('notes', ''),
                "is_sleep": "수면" in str(row.get("event_name", "")),

                # Enriched metadata from tag normalization
                "agency_mode": row.get('agency_mode', 'Maintenance/Organization'),
                "normalized_title": row.get('normalized_title', row.get('event_name', '')),
                "is_risk_recharger": bool(row.get('is_risk_recharger', False)),
                "is_emotional_event": bool(row.get('is_emotional_event', False)),
                "tags": row.get('extracted_tags', []) if pd.notna(row.get('extracted_tags')) else [],
            }

            # CleanedCalendarDocument dict 생성
            cleaned_doc = {
                "original_id": str(row['id']),
                "content": content,
                "ref_date": row['ref_date'],
                "platform": "calendar",
                "doc_type": "calendar_event",
                "author_id": str(row['author_id']),
                "author_full_name": row['author_full_name'],
                "is_valid": True,  # Calendar 데이터는 모두 유효
                "metadata": metadata
            }

            cleaned_docs.append(cleaned_doc)

        return cleaned_docs

    def _synthesize_natural_language_content(self, row: pd.Series) -> str:
        """
        구조화된 캘린더 데이터를 자연어로 변환합니다.

        예시 출력:
        "2024년 1월 15일 월요일, 오전 9시부터 11시까지 2시간 동안 '프로젝트 개발' 활동을 했습니다.
        카테고리: 개인개발. 서브 카테고리: #휴식/회복. 메모: API 설계 및 데이터베이스 스키마 작성 완료."
        """
        start_dt = row['start_datetime']
        end_dt = row['end_datetime']
        duration_minutes = row.get('duration_minutes', 0)
        event_name = row.get('event_name', '활동')
        category = row.get('calendar_name', '')
        sub_category = row.get('sub_category', '')
        notes = row.get('notes', '')

        # 날짜 정보
        weekday_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
        date_str = start_dt.strftime('%Y년 %m월 %d일')
        weekday_str = weekday_map.get(start_dt.weekday(), '')

        # 시간 정보
        start_time_str = start_dt.strftime('%p %I시 %M분').replace('AM', '오전').replace('PM', '오후')
        end_time_str = end_dt.strftime('%p %I시 %M분').replace('AM', '오전').replace('PM', '오후')

        # 시간 제거 (00분인 경우)
        start_time_str = start_time_str.replace(' 00분', '')
        end_time_str = end_time_str.replace(' 00분', '')

        # Duration을 자연어로
        hours = int(duration_minutes // 60)
        minutes = int(duration_minutes % 60)

        if hours > 0 and minutes > 0:
            duration_str = f"{hours}시간 {minutes}분"
        elif hours > 0:
            duration_str = f"{hours}시간"
        else:
            duration_str = f"{minutes}분"

        # 기본 문장 구성
        content_parts = [
            f"{date_str} {weekday_str}요일, {start_time_str}부터 {end_time_str}까지 "
            f"{duration_str} 동안 '{event_name}' 활동을 했습니다."
        ]

        # 카테고리 추가
        if category:
            content_parts.append(f"카테고리: {category}.")

        # 서브 카테고리 추가
        if sub_category and sub_category.strip():
            content_parts.append(f"서브 카테고리: {sub_category}.")

        # 메모 추가
        if notes and notes.strip():
            content_parts.append(f"메모: {notes.strip()}")

        return " ".join(content_parts)
