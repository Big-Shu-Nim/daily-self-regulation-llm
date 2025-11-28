"""
개인정보 필터링 설정 파일 생성 헬퍼 스크립트

Usage:
    python tools/create_privacy_config.py
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from llm_engineering.application.visualization.privacy_utils import create_sample_privacy_config


def main():
    """샘플 개인정보 필터링 설정 파일을 생성합니다."""
    print("=" * 60)
    print("개인정보 필터링 설정 파일 생성")
    print("=" * 60)
    print()

    # 설정 파일 생성
    create_sample_privacy_config()

    print()
    print("=" * 60)
    print("사용 방법:")
    print("=" * 60)
    print()
    print("1. privacy_filter_config.json 파일을 열어 편집하세요")
    print()
    print("2. 이벤트명 + 시간으로 특정 이벤트 마스킹:")
    print('   {')
    print('     "event_name": "프로젝트 작업",')
    print('     "start_time": "22:15",  # HH:MM 형식')
    print('     "date": "2025-11-05"    # YYYY-MM-DD 형식 (선택)')
    print('   }')
    print()
    print("3. 서브카테고리 기반 마스킹 (일/생산 카테고리만):")
    print('   "masked_subcategories": [')
    print('     "이직준비",')
    print('     "이사준비",')
    print('     "재무관리"')
    print('   ]')
    print()
    print("4. 대쉬보드에서 이벤트를 확인하고:")
    print("   - 일/생산, 학습/성장 그래프에서 이벤트명과 시작 시간을 확인")
    print("   - 해당 정보를 설정 파일에 추가")
    print("   - 대쉬보드를 새로고침하면 '개인정보, 마스킹처리됨'으로 표시")
    print()
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
