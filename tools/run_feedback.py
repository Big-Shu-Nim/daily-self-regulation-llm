"""
통합 피드백 생성 스크립트.

In-context 방식으로 일일/주간/월간 피드백을 생성합니다.

Usage:
    # 일일 피드백
    python tools/run_feedback.py daily --date 2025-10-20
    python tools/run_feedback.py daily --date 2025-10-20 --style coach

    # 주간 피드백
    python tools/run_feedback.py weekly --start-date 2025-10-14 --end-date 2025-10-20
    python tools/run_feedback.py weekly --start-date 2025-10-14  # 자동으로 +6일

    # 월간 피드백
    python tools/run_feedback.py monthly --year 2025 --month 10
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse

from llm_engineering.application.feedback import (
    DailyFeedbackGenerator,
    WeeklyFeedbackGenerator,
    MonthlyFeedbackGenerator,
)
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


def run_daily_feedback(args):
    """일일 피드백 생성."""
    print("\n" + "=" * 80)
    print(f"📅 일일 피드백 생성: {args.date}")
    print("=" * 80)
    print(f"프롬프트 스타일: {args.style}")
    print(f"3일 컨텍스트: {'아니오' if args.no_context else '예'}")
    if args.model:
        print(f"LLM 모델: {args.model}")
    print(f"Temperature: {args.temperature}")
    print("=" * 80 + "\n")

    try:
        # 생성기 초기화
        generator = DailyFeedbackGenerator(
            model_id=args.model,
            temperature=args.temperature,
            prompt_style=args.style,
        )

        # 피드백 생성
        print("🤖 피드백 생성 중...")
        feedback = generator.generate(
            target_date=args.date,
            include_previous=not args.no_context,
            include_next=not args.no_context,
            save_to_db=args.save,
        )

        if args.save:
            print("💾 MongoDB에 저장 완료")

        print("✅ 피드백 생성 완료\n")

        # 결과 출력 또는 저장
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

        # 통계 정보
        print("📊 생성 정보")
        print(f"  - 날짜: {args.date}")
        print(f"  - 스타일: {args.style}")
        print(f"  - 길이: {len(feedback)} 글자")
        print()

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def run_weekly_feedback(args):
    """주간 피드백 생성."""
    print("\n" + "=" * 80)
    print(f"📅 주간 피드백 생성: {args.start_date} ~ {args.end_date or '(+6일)'}")
    print("=" * 80)
    print(f"과거 주간 리포트 포함: {'예' if args.include_past_reports else '아니오'}")
    if args.model:
        print(f"LLM 모델: {args.model}")
    print(f"Temperature: {args.temperature}")
    print("=" * 80 + "\n")

    try:
        # 생성기 초기화
        generator = WeeklyFeedbackGenerator(
            model_id=args.model,
            temperature=args.temperature,
        )

        # 피드백 생성
        print("🤖 피드백 생성 중...")
        feedback = generator.generate(
            start_date=args.start_date,
            end_date=args.end_date,
            include_past_reports=args.include_past_reports,
        )

        print("✅ 피드백 생성 완료\n")

        # 결과 출력 또는 저장
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

        # 통계 정보
        print("📊 생성 정보")
        print(f"  - 기간: {args.start_date} ~ {args.end_date or '(+6일)'}")
        print(f"  - 길이: {len(feedback)} 글자")
        print()

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def run_monthly_feedback(args):
    """월간 피드백 생성."""
    print("\n" + "=" * 80)
    print(f"📅 월간 피드백 생성: {args.year}년 {args.month}월")
    print("=" * 80)
    if args.model:
        print(f"LLM 모델: {args.model}")
    print(f"Temperature: {args.temperature}")
    print("=" * 80 + "\n")

    try:
        # 생성기 초기화
        generator = MonthlyFeedbackGenerator(
            model_id=args.model,
            temperature=args.temperature,
        )

        # 피드백 생성
        print("🤖 피드백 생성 중 (계층적 요약)...")
        print("   - 1단계: 주별 요약 생성...")
        feedback = generator.generate(
            year=args.year,
            month=args.month,
        )

        print("✅ 피드백 생성 완료\n")

        # 결과 출력 또는 저장
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

        # 통계 정보
        print("📊 생성 정보")
        print(f"  - 기간: {args.year}년 {args.month}월")
        print(f"  - 길이: {len(feedback)} 글자")
        print()

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="In-context 기반 통합 피드백 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 일일 피드백
  python tools/run_feedback.py daily --date 2025-10-20
  python tools/run_feedback.py daily --date 2025-10-20 --style coach
  python tools/run_feedback.py daily --date 2025-10-20 --no-context

  # 주간 피드백
  python tools/run_feedback.py weekly --start-date 2025-10-14
  python tools/run_feedback.py weekly --start-date 2025-10-14 --end-date 2025-10-20

  # 월간 피드백
  python tools/run_feedback.py monthly --year 2025 --month 10

사용 가능한 프롬프트 스타일 (일일 피드백만):
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

    subparsers = parser.add_subparsers(dest="command", help="피드백 타입")

    # ========== Daily 서브커맨드 ==========
    daily_parser = subparsers.add_parser(
        "daily",
        help="일일 피드백 생성"
    )

    daily_parser.add_argument(
        "--date",
        type=validate_date,
        required=True,
        help="분석할 날짜 (YYYY-MM-DD 형식)"
    )

    daily_parser.add_argument(
        "--style",
        choices=list(PROMPTS_REGISTRY.keys()),
        default="original",
        help="피드백 프롬프트 스타일 (기본: original)"
    )

    daily_parser.add_argument(
        "--no-context",
        action="store_true",
        help="3일 컨텍스트 없이 해당 날짜만 분석"
    )

    daily_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="피드백을 저장할 파일 경로"
    )

    daily_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="사용할 LLM 모델"
    )

    daily_parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature (0.0-1.0, 기본: 0.7)"
    )

    daily_parser.add_argument(
        "--save",
        action="store_true",
        help="MongoDB에 피드백 저장"
    )

    # ========== Weekly 서브커맨드 ==========
    weekly_parser = subparsers.add_parser(
        "weekly",
        help="주간 피드백 생성"
    )

    weekly_parser.add_argument(
        "--start-date",
        type=validate_date,
        required=True,
        help="주 시작 날짜 (YYYY-MM-DD 형식, 월요일 권장)"
    )

    weekly_parser.add_argument(
        "--end-date",
        type=validate_date,
        default=None,
        help="주 종료 날짜 (YYYY-MM-DD 형식, 미지정 시 start-date + 6일)"
    )

    weekly_parser.add_argument(
        "--include-past-reports",
        action="store_true",
        help="과거 주간 리포트 포함 (Notion)"
    )

    weekly_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="피드백을 저장할 파일 경로"
    )

    weekly_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="사용할 LLM 모델"
    )

    weekly_parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature (0.0-1.0, 기본: 0.7)"
    )

    # ========== Monthly 서브커맨드 ==========
    monthly_parser = subparsers.add_parser(
        "monthly",
        help="월간 피드백 생성 (계층적 요약)"
    )

    monthly_parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="연도 (YYYY 형식)"
    )

    monthly_parser.add_argument(
        "--month",
        type=int,
        required=True,
        choices=range(1, 13),
        help="월 (1-12)"
    )

    monthly_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="피드백을 저장할 파일 경로"
    )

    monthly_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="사용할 LLM 모델"
    )

    monthly_parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature (0.0-1.0, 기본: 0.7)"
    )

    # ========== Global 옵션 ==========
    parser.add_argument(
        "--list-styles",
        action="store_true",
        help="사용 가능한 프롬프트 스타일 목록 출력"
    )

    args = parser.parse_args()

    # 스타일 목록 출력
    if args.list_styles:
        print("=" * 80)
        print("사용 가능한 피드백 프롬프트 스타일 (일일 피드백)")
        print("=" * 80)
        for style, info in PROMPTS_REGISTRY.items():
            print(f"\n{style.upper()}")
            print(f"  설명: {info['description']}")
            print(f"  추천: {info['best_for']}")
            print(f"  톤: {info['tone']}")
            print(f"  길이: {info['length']}")
        print("\n" + "=" * 80)
        return

    # 커맨드 실행
    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "daily":
            run_daily_feedback(args)
        elif args.command == "weekly":
            run_weekly_feedback(args)
        elif args.command == "monthly":
            run_monthly_feedback(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")


if __name__ == "__main__":
    main()
