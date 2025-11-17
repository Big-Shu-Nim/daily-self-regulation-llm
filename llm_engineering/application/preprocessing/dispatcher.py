"""
Preprocessor dispatcher for routing data to appropriate preprocessor.

각 데이터 소스별 preprocessor를 관리하고 실행합니다.
"""

from typing import List, Dict, Any, Type

import pandas as pd

from .base import BasePreprocessor
from .calendar import CalendarPreprocessor
from .google_calendar import GoogleCalendarPreprocessor
from .notion import NotionPreprocessor
from .naver import NaverPreprocessor


# Preprocessor 레지스트리
PREPROCESSOR_REGISTRY: Dict[str, Type[BasePreprocessor]] = {
    "calendar": CalendarPreprocessor,
    "google_calendar": GoogleCalendarPreprocessor,
    "notion": NotionPreprocessor,
    "naver": NaverPreprocessor,
}


class PreprocessorDispatcher:
    """
    데이터 소스에 맞는 preprocessor를 선택하여 실행하는 dispatcher.

    사용 예시:
        dispatcher = PreprocessorDispatcher()

        # Calendar 전처리
        calendar_cleaned = dispatcher.preprocess(
            df_calendar,
            preprocessor_type="calendar",
            category_rename_rules=[...]
        )

        # Notion 전처리
        notion_cleaned = dispatcher.preprocess(
            df_notion,
            preprocessor_type="notion"
        )

        # Naver 전처리
        naver_cleaned = dispatcher.preprocess(
            df_naver,
            preprocessor_type="naver",
            filter_categories=['일일피드백']
        )
    """

    def __init__(self, verbose: bool = True):
        """
        Args:
            verbose: 진행 상황 출력 여부
        """
        self.verbose = verbose

    def preprocess(
        self,
        df: pd.DataFrame,
        preprocessor_type: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        지정된 preprocessor를 사용하여 데이터를 전처리합니다.

        Args:
            df: 원본 DataFrame
            preprocessor_type: preprocessor 타입 ("calendar", "notion", "naver")
            **kwargs: preprocessor에 전달할 추가 인자

        Returns:
            Cleaned document dict 리스트

        Raises:
            ValueError: 지원하지 않는 preprocessor 타입인 경우
        """
        if preprocessor_type not in PREPROCESSOR_REGISTRY:
            raise ValueError(
                f"Unsupported preprocessor type: {preprocessor_type}. "
                f"Available types: {list(PREPROCESSOR_REGISTRY.keys())}"
            )

        # Preprocessor 인스턴스 생성
        preprocessor_class = PREPROCESSOR_REGISTRY[preprocessor_type]
        preprocessor = preprocessor_class(verbose=self.verbose, **kwargs)

        # 전처리 실행
        return preprocessor.clean(df)

    def preprocess_all(
        self,
        dataframes: Dict[str, pd.DataFrame],
        configs: Dict[str, dict] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        여러 데이터 소스를 한 번에 전처리합니다.

        Args:
            dataframes: {"calendar": df_calendar, "notion": df_notion, ...}
            configs: 각 preprocessor의 설정 {"calendar": {...}, "notion": {...}, ...}

        Returns:
            {"calendar": [cleaned_docs], "notion": [cleaned_docs], ...}

        사용 예시:
            dispatcher = PreprocessorDispatcher()

            dataframes = {
                "calendar": df_calendar,
                "notion": df_notion,
                "naver": df_naver
            }

            configs = {
                "calendar": {
                    "category_rename_rules": [
                        {"old": "개인개발", "new": "프로젝트", "before_date": "2024-06-01"}
                    ]
                },
                "naver": {
                    "filter_categories": ["일일피드백"]
                }
            }

            all_cleaned = dispatcher.preprocess_all(dataframes, configs)
        """
        configs = configs or {}
        results = {}

        for preprocessor_type, df in dataframes.items():
            if df.empty:
                print(f"⚠️ {preprocessor_type} DataFrame is empty, skipping...")
                results[preprocessor_type] = []
                continue

            config = configs.get(preprocessor_type, {})
            results[preprocessor_type] = self.preprocess(df, preprocessor_type, **config)

        return results

    @staticmethod
    def get_available_preprocessors() -> List[str]:
        """사용 가능한 preprocessor 타입 목록을 반환합니다."""
        return list(PREPROCESSOR_REGISTRY.keys())

    @staticmethod
    def register_preprocessor(name: str, preprocessor_class: Type[BasePreprocessor]):
        """
        새로운 preprocessor를 레지스트리에 등록합니다.

        Args:
            name: preprocessor 이름
            preprocessor_class: BasePreprocessor를 상속한 클래스
        """
        if not issubclass(preprocessor_class, BasePreprocessor):
            raise ValueError(
                f"{preprocessor_class} must inherit from BasePreprocessor"
            )
        PREPROCESSOR_REGISTRY[name] = preprocessor_class
