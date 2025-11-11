"""
Calendar data preprocessor.

구조화된 캘린더 데이터를 자연어 형태로 변환하여 임베딩에 적합한 형태로 만듭니다.
9가지 카테고리별 전문화된 전처리를 수행합니다.
"""

from typing import List, Dict, Any
import re

import pandas as pd

from .base import BasePreprocessor
from .utils import parse_content_field


class CalendarPreprocessor(BasePreprocessor):
    """
    Calendar 데이터를 전처리하는 클래스.

    핵심 작업:
    1. content 필드 파싱 (event_name, notes 추출)
    2. 자정을 넘는 활동 분할
    3. 조건부 카테고리 이름 변경
    4. 9가지 카테고리별 전문화된 전처리:
       - 학습/성장: 방법_대상 파싱
       - 일/생산: #태그 추출 및 빈도 분석
       - Daily/chore: 운전 감지 및 제목 변경
       - Drain: #인간관계, #감정이벤트 태그 추출
       - 운동: 무산소/유산소 분류
       - 휴식/회복: risky recharger 감지
       - 기타 카테고리들
    5. 구조화 데이터를 자연어로 변환 (임베딩용 content 생성)
    """


    # 운동 분류 키워드
    ANAEROBIC_KEYWORDS = [
        "무산소", "웨이트", "헬스", "근력", "벤치프레스", "스쿼트", "데드리프트",
        "덤벨", "바벨", "풀업", "턱걸이", "푸쉬업", "팔굽혀펴기", "플랭크"
    ]

    AEROBIC_KEYWORDS = [
        "유산소", "러닝", "달리기", "조깅", "걷기", "산책", "자전거", "사이클","스텝퍼",
        "수영", "에어로빅", "줌바", "댄스", "트레드밀", "런닝머신", "계단", "등산"
    ]

    # Risky recharger 키워드
    RISKY_RECHARGER_KEYWORDS = [
        "혼술", "유투브", "유튜브", "넷플릭스", "netflix", "영화", "드라마",
        "게임", "핸드폰", "폰", "인스타", "instagram", "페이스북", "facebook"
    ]

    # 운전 관련 키워드
    DRIVING_KEYWORDS = ["운전"]

    # 인간관계 재분류: 유지/정리로 갈 키워드 (나머지는 휴식/회복)
    RELATIONSHIP_MAINTENANCE_KEYWORDS = ["카톡", "연락"]

    # 식사 관련 키워드 (정규화용)
    MEAL_KEYWORDS = ["식사", "아침식사", "점심식사", "저녁식사", "조식", "중식", "석식"]

    # Daily/Chore에 남아야 할 식사 관련 활동
    MEAL_PREPARATION_KEYWORDS = ["식사준비", "식사 준비"]

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

        # 4. 자정 분할 (수면은 종료 날짜 기준)
        df = self._split_across_midnight(df)
        self.log(f"✅ 자정 분할 완료: {len(df)}건")

        # 5. 카테고리 이름 변경
        df = self._rename_categories(df)

        # 6. 9가지 카테고리별 전처리
        df = self._apply_category_specific_preprocessing(df)
        self.log("✅ 카테고리별 전처리 완료")

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

    def _split_across_midnight(self, df: pd.DataFrame) -> pd.DataFrame:
        """자정을 넘는 활동을 분할"""
        processed_rows = []
        for _, row in df.iterrows():
            processed_rows.extend(self._split_row_across_midnight(row))

        df_processed = pd.DataFrame(processed_rows)
        return df_processed

    def _split_row_across_midnight(self, row: pd.Series) -> List[Dict[str, Any]]:
        """
        활동을 00시 기준으로 분할합니다.
        - 수면 활동: 종료 날짜 기준, 분할하지 않음
        - 기타 활동: 00시를 넘으면 분할
        """
        data = row.to_dict()
        start_dt = data['start_datetime']
        end_dt = data['end_datetime']
        is_sleep = "수면" in str(data.get("event_name", ""))

        # 수면 활동 처리 (종료 날짜 기준)
        if is_sleep:
            data['duration_minutes'] = (end_dt - start_dt).total_seconds() / 60
            return [data]

        # 같은 날짜면 분할 불필요
        if start_dt.date() == end_dt.date():
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
            new_row['duration_minutes'] = (split_end_dt - current_dt).total_seconds() / 60
            result_rows.append(new_row)

            current_dt = split_end_dt

        return result_rows

    def _rename_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """조건부 카테고리 이름 변경"""
        if 'start_datetime' not in df.columns:
            return df

        for rule in self.category_rename_rules:
            target_name = rule['old']
            new_name = rule['new']
            cutoff_date = rule['before_date']

            # start_datetime을 날짜로 변환하여 비교
            condition = (
                df['start_datetime'].dt.strftime('%Y-%m-%d') <= cutoff_date
            ) & (df['calendar_name'] == target_name)

            count = condition.sum()
            df.loc[condition, 'calendar_name'] = new_name

            if count > 0:
                self.log(f"🔄 '{target_name}' → '{new_name}' 변경: {count}건 (기준일: {cutoff_date})")

        return df

    def _apply_category_specific_preprocessing(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        9가지 카테고리별 전문화된 전처리를 수행합니다.

        카테고리:
        1. 학습/성장: 방법_대상 파싱
        2. 일/생산: #태그 추출
        3. Daily/chore: 운전 감지
        4. Drain: #인간관계, #감정이벤트
        5. 운동: 무산소/유산소 분류
        6. 휴식/회복: risky recharger 감지
        7. 수면: 기본 처리
        8. 유지/정리: #인간관계 추출
        9. 인간관계: 기본 처리
        """
        # 메타데이터 컬럼 초기화
        df['processed_event_name'] = df['event_name']
        df['processed_notes'] = df['notes']
        df['extracted_tags'] = None
        df['learning_method'] = None
        df['learning_target'] = None
        df['work_tags'] = None
        df['exercise_type'] = None
        df['is_risky_recharger'] = False
        df['has_emotion_event'] = False
        df['has_relationship_tag'] = False

        for idx, row in df.iterrows():
            document_id = str(row['id'])
            category = row.get('calendar_name', '')
            sub_category = row.get('sub_category', '') or ''
            event_name = row.get('event_name', '')
            notes = row.get('notes', '') or ''


            # 인간관계 카테고리 재분류
            if category == "인간관계":
                # #인간관계 태그 보장
                if not sub_category or "#인간관계" not in sub_category:
                    df.at[idx, 'sub_category'] = "#인간관계"
                    sub_category = "#인간관계"

                # 이벤트 이름 기반 재분류
                if event_name:
                    event_name_lower = event_name.lower()
                    # "카톡" 또는 "연락" → 유지/정리
                    if any(keyword in event_name_lower for keyword in self.RELATIONSHIP_MAINTENANCE_KEYWORDS):
                        df.at[idx, 'calendar_name'] = "유지 / 정리"
                        category = "유지 / 정리"
                    else:
                        # 그 외 → 휴식/회복
                        df.at[idx, 'calendar_name'] = "휴식 / 회복"
                        category = "휴식 / 회복"
                else:
                    # 이벤트 이름이 없으면 기본으로 휴식/회복
                    df.at[idx, 'calendar_name'] = "휴식 / 회복"
                    category = "휴식 / 회복"

            # Daily/Chore 식사 → 휴식/회복 재분류 (식사준비 제외)
            if category == "Daily / Chore" and event_name:
                event_name_lower = event_name.lower()
                # 식사준비가 아니고 식사 키워드가 있으면 휴식/회복으로
                is_meal_prep = any(keyword in event_name_lower for keyword in self.MEAL_PREPARATION_KEYWORDS)
                is_meal = any(keyword in event_name_lower for keyword in self.MEAL_KEYWORDS)

                if is_meal and not is_meal_prep:
                    df.at[idx, 'calendar_name'] = "휴식 / 회복"
                    category = "휴식 / 회복"

            # 카테고리별 전처리
            if category == "학습 / 성장":
                self._preprocess_learning(df, idx, event_name)

            elif category == "일 / 생산":
                self._preprocess_work(df, idx, sub_category)

            elif category == "Daily / Chore":
                self._preprocess_daily_chore(df, idx, event_name, notes)

            elif category == "Drain":
                self._preprocess_drain(df, idx, sub_category)

            elif category == "운동":
                self._preprocess_exercise(df, idx, event_name, sub_category)

            elif category == "휴식 / 회복":
                self._preprocess_rest(df, idx, event_name, sub_category)

            elif category == "유지 / 정리":
                self._preprocess_maintenance(df, idx, sub_category)

            # 공통: 전체 태그 추출 (#인간관계, #감정이벤트 등)
            all_tags = self._extract_all_tags(sub_category)
            df.at[idx, 'extracted_tags'] = all_tags

            if "#인간관계" in all_tags:
                df.at[idx, 'has_relationship_tag'] = True
            if "#감정이벤트" in all_tags:
                df.at[idx, 'has_emotion_event'] = True

        return df

    def _preprocess_learning(self, df: pd.DataFrame, idx: int, event_name: str):
        """
        학습/성장 카테고리 전처리
        이벤트 이름 형식: 방법_대상
        예: 독서_LLM을 활용한 실전 AI 애플리케이션개발_허정준
        """
        if not event_name or "_" not in event_name:
            return

        parts = event_name.split("_", 1)
        if len(parts) >= 2:
            method = parts[0].strip()  # 방법 (예: 독서)
            target = parts[1].strip()   # 대상 (예: LLM을 활용한...)

            df.at[idx, 'learning_method'] = method
            df.at[idx, 'learning_target'] = target

    def _preprocess_work(self, df: pd.DataFrame, idx: int, sub_category: str):
        """
        일/생산 카테고리 전처리
        Sub Category에서 #태그 추출
        예: #기획 #구현 #실행
        """
        if not sub_category:
            return

        # # 로 시작하는 모든 태그 추출
        tags = re.findall(r'#\S+', sub_category)
        if tags:
            df.at[idx, 'work_tags'] = tags

    def _preprocess_daily_chore(
        self,
        df: pd.DataFrame,
        idx: int,
        event_name: str,
        notes: str
    ):
        """
        Daily/chore 카테고리 전처리
        운전 감지: 이벤트 이름 또는 노트에 '운전'이 있으면 제목을 '운전'으로 변경하고
        기존 내용은 notes에 담음
        """
        combined_text = f"{event_name or ''} {notes or ''}".lower()

        is_driving = any(keyword in combined_text for keyword in self.DRIVING_KEYWORDS)

        if is_driving and event_name:
            # 기존 제목을 notes에 추가 (notes가 없으면)
            original_title = event_name
            if notes:
                new_notes = f"{original_title} - {notes}"
            else:
                new_notes = original_title

            df.at[idx, 'processed_event_name'] = "운전"
            df.at[idx, 'processed_notes'] = new_notes

    def _preprocess_drain(self, df: pd.DataFrame, idx: int, sub_category: str):
        """
        Drain 카테고리 전처리
        #인간관계, #감정이벤트 태그 추출
        """
        # 태그는 공통 로직에서 처리됨
        pass

    def _preprocess_exercise(
        self,
        df: pd.DataFrame,
        idx: int,
        event_name: str,
        sub_category: str
    ):
        """
        운동 카테고리 전처리
        제목과 Sub category를 분석해서 무산소/유산소 분류
        """
        combined_text = f"{event_name or ''} {sub_category or ''}".lower()

        has_anaerobic = any(kw in combined_text for kw in self.ANAEROBIC_KEYWORDS)
        has_aerobic = any(kw in combined_text for kw in self.AEROBIC_KEYWORDS)

        if has_anaerobic and not has_aerobic:
            df.at[idx, 'exercise_type'] = "무산소"
        elif has_aerobic and not has_anaerobic:
            df.at[idx, 'exercise_type'] = "유산소"
        elif has_anaerobic and has_aerobic:
            df.at[idx, 'exercise_type'] = "복합"
        else:
            df.at[idx, 'exercise_type'] = "기타"

    def _preprocess_rest(
        self,
        df: pd.DataFrame,
        idx: int,
        event_name: str,
        sub_category: str
    ):
        """
        휴식/회복 카테고리 전처리
        1. 식사 관련 이벤트 이름 정규화
        2. #즉시만족 태그 또는 risky recharger 키워드 감지
        """
        # 1. 식사 이름 정규화
        if event_name:
            event_name_lower = event_name.lower()
            # 식사 관련 키워드가 있으면 "식사"로 통일
            if any(keyword in event_name_lower for keyword in self.MEAL_KEYWORDS):
                df.at[idx, 'processed_event_name'] = "식사"

        # 2. Risky recharger 감지
        is_risky = False

        # 2-1. #즉시만족 태그 확인
        if sub_category and "#즉시만족" in sub_category:
            is_risky = True

        # 2-2. 이벤트 이름에서 risky 키워드 확인
        if event_name:
            event_name_lower = event_name.lower()
            if any(kw in event_name_lower for kw in self.RISKY_RECHARGER_KEYWORDS):
                is_risky = True

        df.at[idx, 'is_risky_recharger'] = is_risky

    def _preprocess_maintenance(self, df: pd.DataFrame, idx: int, sub_category: str):
        """
        유지/정리 카테고리 전처리
        #인간관계 태그 추출 (공통 로직에서 처리됨)
        """
        # 공통 로직에서 태그 처리됨
        pass

    def _extract_all_tags(self, sub_category: str) -> List[str]:
        """Sub Category에서 모든 # 태그 추출"""
        if not sub_category:
            return []

        tags = re.findall(r'#\S+', sub_category)
        return tags

    def _to_cleaned_documents(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        DataFrame을 CleanedCalendarDocument dict 리스트로 변환.
        구조화 데이터를 자연어 content로 변환하는 핵심 로직.
        """
        cleaned_docs = []

        for _, row in df.iterrows():
            # 자연어 content 생성
            content = self._synthesize_natural_language_content(row)

            # ref_date 계산 (수면은 종료 날짜, 나머지는 시작 날짜)
            is_sleep = "수면" in str(row.get("event_name", ""))
            if is_sleep:
                ref_date = row['end_datetime'].strftime('%Y-%m-%d')
            else:
                ref_date = row['start_datetime'].strftime('%Y-%m-%d')

            # Metadata 구성
            metadata = {
                "start_datetime": row['start_datetime'].isoformat() if pd.notna(row['start_datetime']) else None,
                "end_datetime": row['end_datetime'].isoformat() if pd.notna(row['end_datetime']) else None,
                "duration_minutes": int(row['duration_minutes']) if pd.notna(row['duration_minutes']) else 0,
                "category_name": row.get('calendar_name', ''),
                "original_event_name": row.get('event_name', ''),
                "event_name": row.get('processed_event_name', row.get('event_name', '')),
                "notes": row.get('processed_notes', row.get('notes', '')),
                "sub_category": row.get('sub_category', ''),
                "is_sleep": is_sleep,

                # 카테고리별 전문화된 메타데이터
                "extracted_tags": row.get('extracted_tags') if row.get('extracted_tags') is not None else [],
                "learning_method": row.get('learning_method'),
                "learning_target": row.get('learning_target'),
                "work_tags": row.get('work_tags') if row.get('work_tags') is not None else [],
                "exercise_type": row.get('exercise_type'),
                "is_risky_recharger": bool(row.get('is_risky_recharger', False)),
                "has_emotion_event": bool(row.get('has_emotion_event', False)),
                "has_relationship_tag": bool(row.get('has_relationship_tag', False)),
            }

            # CleanedCalendarDocument dict 생성
            cleaned_doc = {
                "original_id": str(row['id']),
                "content": content,
                "ref_date": ref_date,
                "platform": "calendar",
                "doc_type": "calendar_event",
                "author_id": str(row['author_id']),
                "author_full_name": row['author_full_name'],
                "is_valid": True,
                "metadata": metadata
            }

            cleaned_docs.append(cleaned_doc)

        return cleaned_docs

    def _synthesize_natural_language_content(self, row: pd.Series) -> str:
        """
        구조화된 캘린더 데이터를 자연어로 변환합니다.
        카테고리별 특수 정보를 포함합니다.

        예시 출력:
        "2024년 1월 15일 월요일, 오전 9시부터 11시까지 2시간 동안 '프로젝트 개발' 활동을 했습니다.
        카테고리: 일/생산. 작업 태그: #기획, #구현. 메모: API 설계 완료."
        """
        start_dt = row['start_datetime']
        end_dt = row['end_datetime']
        duration_minutes = row.get('duration_minutes', 0)
        event_name = row.get('processed_event_name', row.get('event_name', '활동'))
        category = row.get('calendar_name', '')
        sub_category = row.get('sub_category', '')
        notes = row.get('processed_notes', row.get('notes', ''))

        # 날짜 정보
        weekday_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
        date_str = start_dt.strftime('%Y년 %m월 %d일')
        weekday_str = weekday_map.get(start_dt.weekday(), '')

        # 시간 정보
        start_time_str = start_dt.strftime('%p %I시 %M분').replace('AM', '오전').replace('PM', '오후')
        end_time_str = end_dt.strftime('%p %I시 %M분').replace('AM', '오전').replace('PM', '오후')

        # 00분 제거
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

        # 카테고리별 특수 정보 추가
        if category == "학습 / 성장":
            method = row.get('learning_method')
            target = row.get('learning_target')
            if method and target:
                content_parts.append(f"학습 방법: {method}. 학습 대상: {target}.")

        elif category == "일 / 생산":
            work_tags = row.get('work_tags')
            if work_tags and len(work_tags) > 0:
                tags_str = ", ".join(work_tags)
                content_parts.append(f"작업 태그: {tags_str}.")

        elif category == "운동":
            exercise_type = row.get('exercise_type')
            if exercise_type:
                content_parts.append(f"운동 유형: {exercise_type}.")

        elif category == "휴식 / 회복":
            is_risky = row.get('is_risky_recharger', False)
            if is_risky:
                content_parts.append("즉시만족형 휴식.")

        # 서브 카테고리 추가
        if sub_category and sub_category.strip():
            content_parts.append(f"서브 카테고리: {sub_category}.")

        # 공통 태그 정보
        extracted_tags = row.get('extracted_tags', [])
        if extracted_tags and len(extracted_tags) > 0:
            # work_tags와 중복되지 않는 태그만 표시
            work_tags = row.get('work_tags') or []
            unique_tags = [tag for tag in extracted_tags if tag not in work_tags]
            if unique_tags:
                tags_str = ", ".join(unique_tags)
                content_parts.append(f"태그: {tags_str}.")

        # 메모 추가
        if notes and notes.strip():
            content_parts.append(f"메모: {notes.strip()}")

        return " ".join(content_parts)
