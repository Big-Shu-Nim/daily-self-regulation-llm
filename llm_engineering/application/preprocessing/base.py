"""
Base preprocessor class for all data sources.

모든 preprocessor는 이 base class를 상속받아 clean() 메서드를 구현합니다.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

import pandas as pd


class BasePreprocessor(ABC):
    """
    데이터 전처리를 위한 base class.

    각 데이터 소스별 preprocessor는 이 클래스를 상속받아:
    1. clean() 메서드를 구현 (핵심 로직)
    2. 필요시 추가 helper 메서드 정의
    """

    def __init__(self, verbose: bool = True):
        """
        Args:
            verbose: 진행 상황 출력 여부
        """
        self.verbose = verbose

    @abstractmethod
    def clean(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        DataFrame을 전처리하여 cleaned document dict 리스트로 변환합니다.

        Args:
            df: 원본 DataFrame

        Returns:
            CleanedDocument에 맞는 dict 리스트
        """
        pass

    def log(self, message: str):
        """진행 상황 로깅"""
        if self.verbose:
            print(message)

    def _validate_dataframe(self, df: pd.DataFrame, required_columns: List[str]):
        """
        DataFrame이 필요한 컬럼을 가지고 있는지 검증합니다.

        Args:
            df: 검증할 DataFrame
            required_columns: 필수 컬럼 리스트

        Raises:
            ValueError: 필수 컬럼이 없을 경우
        """
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}. "
                f"Available columns: {list(df.columns)}"
            )
