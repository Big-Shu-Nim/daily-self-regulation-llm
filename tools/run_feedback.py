"""
일일 피드백 생성 스크립트.

RAG 기반으로 특정 날짜의 행동 데이터를 분석하여 피드백을 생성합니다.

Usage:
    python tools/run_feedback.py --date 2025-10-20
    python tools/run_feedback.py --date 2025-10-20 --style coach
    python tools/run_feedback.py --date 2025-10-20 --source calendar
    python tools/run_feedback.py --date 2025-10-20 --output feedback_20251020.md
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse

from llm_engineering.application.rag import DocumentRetriever, FeedbackChain
from llm_engineering.application.prompts.feedback_prompts import PROMPTS_REGISTRY


def validate_date(date_string: str) -> str:
    """날짜 형식을 검증합니다."""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return date_string
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_string}. Expected format: YYYY-MM-DD"
        )


def main():
    parser = argparse.ArgumentParser(
        description="RAG 기반 일일 피드백 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 2025년 10월 20일 피드백 생성 (original 스타일)
  python tools/run_feedback.py --date 2025-10-20

  # Coach 스타일로 생성
  python tools/run_feedback.py --date 2025-10-20 --style coach

  # Calendar 소스만 사용
  python tools/run_feedback.py --date 2025-10-20 --source calendar

  # 파일로 저장
  python tools/run_feedback.py --date 2025-10-20 --output feedback.md

  # 3일 컨텍스트 없이 해당일만
  python tools/run_feedback.py --date 2025-10-20 --no-context

사용 가능한 프롬프트 스타일:
  - original: 균형잡힌 공감적 분석 (기본)
  - minimal: 간결한 실용주의 버전
  - coach: 동기부여 중심 코칭 스타일
  - scientist: 객관적 데이터 중심 분석
  - cbt: 인지행동치료 기반 패턴 분석
  - narrative: 스토리텔링 서사 구조
  - dashboard: 시각적 대시보드 형식
  - metacognitive: 메타인지 강화 버전
        """
    )

    parser.add_argument(
        "--date",
        type=validate_date,
        required=True,
        help="분석할 날짜 (YYYY-MM-DD 형식, 예: 2025-10-20)"
    )

    parser.add_argument(
        "--style",
        choices=list(PROMPTS_REGISTRY.keys()),
        default="original",
        help="피드백 프롬프트 스타일 (기본: original)"
    )

    parser.add_argument(
        "--source",
        choices=["calendar", "notion", "naver", "all"],
        default="all",
        help="검색할 데이터 소스 (기본: all)"
    )

    parser.add_argument(
        "--no-context",
        action="store_true",
        help="3일 컨텍스트 없이 해당 날짜만 분석 (전날/다음날 데이터 제외)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="피드백을 저장할 파일 경로 (지정하지 않으면 화면에 출력)"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="사용할 LLM 모델 (기본: settings.OPENAI_MODEL_ID)"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature (0.0-1.0, 기본: 0.7)"
    )

    parser.add_argument(
        "--list-styles",
        action="store_true",
        help="사용 가능한 프롬프트 스타일 목록 출력"
    )

    args = parser.parse_args()

    # 스타일 목록 출력
    if args.list_styles:
        print("=" * 80)
        print("사용 가능한 피드백 프롬프트 스타일")
        print("=" * 80)
        for style, info in PROMPTS_REGISTRY.items():
            print(f"\n{style.upper()}")
            print(f"  설명: {info['description']}")
            print(f"  추천: {info['best_for']}")
            print(f"  톤: {info['tone']}")
            print(f"  길이: {info['length']}")
        print("\n" + "=" * 80)
        return

    print("\n" + "=" * 80)
    print(f"일일 피드백 생성: {args.date}")
    print("=" * 80)
    print(f"프롬프트 스타일: {args.style}")
    print(f"데이터 소스: {args.source}")
    print(f"3일 컨텍스트: {'아니오' if args.no_context else '예'}")
    if args.model:
        print(f"LLM 모델: {args.model}")
    print(f"Temperature: {args.temperature}")
    print("=" * 80 + "\n")

    try:
        # 1. 문서 검색
        print("📚 1. 관련 문서 검색 중...")
        retriever = DocumentRetriever()

        retrieved_docs = retriever.retrieve_by_date_range(
            target_date=args.date,
            include_previous=not args.no_context,
            include_next=not args.no_context,
            source=args.source
        )

        # 검색 결과 요약
        day1_count = len(retrieved_docs.get("day1", []))
        day2_count = len(retrieved_docs.get("day2", []))
        day3_count = len(retrieved_docs.get("day3", []))

        print(f"  - Day 1 (전날): {day1_count}건")
        print(f"  - Day 2 (분석일): {day2_count}건")
        print(f"  - Day 3 (다음날): {day3_count}건")
        print(f"  총 {day1_count + day2_count + day3_count}건 검색 완료\n")

        if day2_count == 0:
            print(f"⚠️  {args.date} 날짜의 데이터가 없습니다.")
            print("   먼저 데이터를 크롤링하고 임베딩하세요:")
            print("   1. python tools/run_crawler.py")
            print("   2. python tools/run_embedding.py")
            return

        # 2. 피드백 생성
        print("🤖 2. LLM 피드백 생성 중...")
        chain = FeedbackChain(
            model_id=args.model,
            temperature=args.temperature,
            prompt_style=args.style
        )

        feedback = chain.generate_feedback(
            retrieved_docs=retrieved_docs,
            target_date=args.date
        )

        print("✅ 피드백 생성 완료\n")

        # 3. 결과 출력 또는 저장
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(feedback)

            print(f"💾 피드백이 저장되었습니다: {output_path}")
            print(f"   파일 크기: {len(feedback)} 글자\n")
        else:
            print("=" * 80)
            print(feedback)
            print("=" * 80 + "\n")

        # 4. 통계 정보
        print("📊 생성 정보")
        print(f"  - 날짜: {args.date}")
        print(f"  - 스타일: {args.style}")
        print(f"  - 모델: {args.model or 'default'}")
        print(f"  - 길이: {len(feedback)} 글자")
        print(f"  - 소스: {args.source}")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
