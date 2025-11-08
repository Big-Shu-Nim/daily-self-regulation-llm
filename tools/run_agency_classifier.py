"""
Agency Role Classification Script.

cleaned_calendar 문서를 재분류하여 agency_role을 추가합니다.

Usage:
    # 일일 재분류
    python tools/run_agency_classifier.py daily --date 2025-10-20

    # 주간 재분류
    python tools/run_agency_classifier.py weekly --start-date 2025-10-14

    # 월간 재분류 (기본 배치 단위)
    python tools/run_agency_classifier.py monthly --year 2025 --month 10

    # Dry-run (DB 저장 안 함)
    python tools/run_agency_classifier.py monthly --year 2025 --month 10 --dry-run
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
from datetime import datetime

from llm_engineering.application.preprocessing.agency_classifier import AgencyClassifier


def validate_date(date_string: str) -> str:
    """날짜 형식을 검증합니다."""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return date_string
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_string}. Expected format: YYYY-MM-DD"
        )


def run_daily_classification(args):
    """일일 재분류 실행."""
    print("\n" + "=" * 80)
    print(f"📊 일일 Agency Role Classification: {args.date}")
    print("=" * 80)
    print(f"LLM 모델: {args.model}")
    print(f"Temperature: {args.temperature}")
    if args.first_name and args.last_name:
        print(f"작성자: {args.first_name} {args.last_name}")
    if args.dry_run:
        print("⚠️  DRY-RUN 모드 (DB 저장 안 함)")
    print("=" * 80 + "\n")

    try:
        # Author full name
        author_full_name = None
        if args.first_name and args.last_name:
            author_full_name = f"{args.first_name} {args.last_name}"

        # Initialize classifier
        classifier = AgencyClassifier(
            model_id=args.model,
            temperature=args.temperature,
            author_full_name=author_full_name,
        )

        # Run classification
        print("🔄 재분류 시작...\n")
        classifications = classifier.classify_day(
            target_date=args.date,
            save_to_db=not args.dry_run,
            skip_processed=args.skip_processed,
        )

        _print_results(classifications, args.dry_run)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def run_weekly_classification(args):
    """주간 재분류 실행."""
    print("\n" + "=" * 80)
    print(f"📊 주간 Agency Role Classification: {args.start_date} ~ {args.end_date or '(+6일)'}")
    print("=" * 80)
    print(f"LLM 모델: {args.model}")
    print(f"Temperature: {args.temperature}")
    if args.first_name and args.last_name:
        print(f"작성자: {args.first_name} {args.last_name}")
    if args.dry_run:
        print("⚠️  DRY-RUN 모드 (DB 저장 안 함)")
    print("=" * 80 + "\n")

    try:
        # Author full name
        author_full_name = None
        if args.first_name and args.last_name:
            author_full_name = f"{args.first_name} {args.last_name}"

        # Initialize classifier
        classifier = AgencyClassifier(
            model_id=args.model,
            temperature=args.temperature,
            author_full_name=author_full_name,
        )

        # Run classification
        print("🔄 재분류 시작...\n")
        classifications = classifier.classify_week(
            start_date=args.start_date,
            end_date=args.end_date,
            save_to_db=not args.dry_run,
            skip_processed=args.skip_processed,
        )

        _print_results(classifications, args.dry_run)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def run_monthly_classification(args):
    """월간 재분류 실행."""
    print("\n" + "=" * 80)
    print(f"📊 월간 Agency Role Classification: {args.year}년 {args.month}월")
    print("=" * 80)
    print(f"LLM 모델: {args.model}")
    print(f"Temperature: {args.temperature}")
    if args.first_name and args.last_name:
        print(f"작성자: {args.first_name} {args.last_name}")
    print(f"병렬 처리: {'✓ 활성화' if args.parallel else '✗ 비활성화'}")
    print(f"이미 처리된 문서 스킵: {'✓ 예' if args.skip_processed else '✗ 아니오'}")
    if args.dry_run:
        print("⚠️  DRY-RUN 모드 (DB 저장 안 함)")
    print("=" * 80 + "\n")

    try:
        # Author full name
        author_full_name = None
        if args.first_name and args.last_name:
            author_full_name = f"{args.first_name} {args.last_name}"

        # Initialize classifier
        classifier = AgencyClassifier(
            model_id=args.model,
            temperature=args.temperature,
            author_full_name=author_full_name,
        )

        # Run classification
        mode_msg = "병렬" if args.parallel else "순차"
        print(f"🔄 재분류 시작 (월 단위 배치, {mode_msg} 처리)...\n")
        classifications = classifier.classify_month(
            year=args.year,
            month=args.month,
            save_to_db=not args.dry_run,
            skip_processed=args.skip_processed,
            parallel=args.parallel,
        )

        _print_results(classifications, args.dry_run)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def _print_results(classifications: list, is_dry_run: bool):
    """재분류 결과를 출력합니다."""
    if not classifications:
        print("❌ 재분류할 문서가 없습니다.\n")
        return

    print("\n✅ 재분류 완료\n")

    # Summary statistics
    print("=" * 80)
    print("📊 재분류 통계")
    print("=" * 80)

    total = len(classifications)
    agency_roles = {}
    risky_count = 0

    for c in classifications:
        role = c.get("agency_role", "unknown")
        agency_roles[role] = agency_roles.get(role, 0) + 1
        if c.get("risky_recharger", False):
            risky_count += 1

    print(f"\n총 문서 수: {total}개\n")
    print("Agency Role 분포:")
    for role, count in sorted(agency_roles.items(), key=lambda x: -x[1]):
        percentage = (count / total) * 100
        print(f"  - {role}: {count}개 ({percentage:.1f}%)")

    if risky_count > 0:
        print(f"\n⚠️  Risky Recharger: {risky_count}개")

    print("\n" + "=" * 80)

    # Sample output (first 5)
    if total > 0:
        print("\n샘플 결과 (최초 5개):\n")
        for i, c in enumerate(classifications[:5], 1):
            print(f"{i}. Document ID: {c.get('document_id', 'N/A')[:8]}...")
            print(f"   Agency Role: {c.get('agency_role', 'unknown')}")
            print(f"   효과 요약: {c.get('after_effect_summary', 'N/A')}")
            if c.get('risky_recharger'):
                print(f"   ⚠️  Risky Recharger")
            print()

    if is_dry_run:
        print("⚠️  DRY-RUN 모드: MongoDB에 저장되지 않았습니다.")
    else:
        print("💾 MongoDB 업데이트 완료")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Agency Role Classification for Calendar Data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 일일 재분류
  python tools/run_agency_classifier.py daily --date 2025-10-20

  # 주간 재분류
  python tools/run_agency_classifier.py weekly --start-date 2025-10-14

  # 월간 재분류 (기본 배치 단위, 권장)
  python tools/run_agency_classifier.py monthly --year 2025 --month 10

  # Dry-run (DB 저장 안 함)
  python tools/run_agency_classifier.py monthly --year 2025 --month 10 --dry-run
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="재분류 단위")

    # ========== Daily 서브커맨드 ==========
    daily_parser = subparsers.add_parser("daily", help="일일 재분류")

    daily_parser.add_argument(
        "--date",
        type=validate_date,
        required=True,
        help="대상 날짜 (YYYY-MM-DD 형식)",
    )

    daily_parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="LLM 모델 (기본: gpt-4o-mini)",
    )

    daily_parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (0.0-1.0, 기본: 0.3)",
    )

    daily_parser.add_argument(
        "--first-name",
        type=str,
        default=None,
        help="작성자 이름 (필터링용)",
    )

    daily_parser.add_argument(
        "--last-name",
        type=str,
        default=None,
        help="작성자 성 (필터링용)",
    )

    daily_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 저장하지 않고 결과만 출력",
    )

    daily_parser.add_argument(
        "--skip-processed",
        action="store_true",
        default=True,
        help="이미 agency_role이 있는 문서 스킵 (기본: True)",
    )

    daily_parser.add_argument(
        "--no-skip-processed",
        action="store_false",
        dest="skip_processed",
        help="모든 문서 재분류 (이미 처리된 문서도 다시 처리)",
    )

    # ========== Weekly 서브커맨드 ==========
    weekly_parser = subparsers.add_parser("weekly", help="주간 재분류")

    weekly_parser.add_argument(
        "--start-date",
        type=validate_date,
        required=True,
        help="주 시작 날짜 (YYYY-MM-DD 형식)",
    )

    weekly_parser.add_argument(
        "--end-date",
        type=validate_date,
        default=None,
        help="주 종료 날짜 (YYYY-MM-DD 형식, 미지정 시 +6일)",
    )

    weekly_parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="LLM 모델 (기본: gpt-4o-mini)",
    )

    weekly_parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (0.0-1.0, 기본: 0.3)",
    )

    weekly_parser.add_argument(
        "--first-name",
        type=str,
        default=None,
        help="작성자 이름 (필터링용)",
    )

    weekly_parser.add_argument(
        "--last-name",
        type=str,
        default=None,
        help="작성자 성 (필터링용)",
    )

    weekly_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 저장하지 않고 결과만 출력",
    )

    weekly_parser.add_argument(
        "--skip-processed",
        action="store_true",
        default=True,
        help="이미 agency_role이 있는 문서 스킵 (기본: True)",
    )

    weekly_parser.add_argument(
        "--no-skip-processed",
        action="store_false",
        dest="skip_processed",
        help="모든 문서 재분류 (이미 처리된 문서도 다시 처리)",
    )

    # ========== Monthly 서브커맨드 ==========
    monthly_parser = subparsers.add_parser("monthly", help="월간 재분류 (권장)")

    monthly_parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="연도 (YYYY 형식)",
    )

    monthly_parser.add_argument(
        "--month",
        type=int,
        required=True,
        choices=range(1, 13),
        help="월 (1-12)",
    )

    monthly_parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="LLM 모델 (기본: gpt-4o-mini)",
    )

    monthly_parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (0.0-1.0, 기본: 0.3)",
    )

    monthly_parser.add_argument(
        "--first-name",
        type=str,
        default=None,
        help="작성자 이름 (필터링용)",
    )

    monthly_parser.add_argument(
        "--last-name",
        type=str,
        default=None,
        help="작성자 성 (필터링용)",
    )

    monthly_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 저장하지 않고 결과만 출력",
    )

    monthly_parser.add_argument(
        "--skip-processed",
        action="store_true",
        default=True,
        help="이미 agency_role이 있는 문서 스킵 (기본: True)",
    )

    monthly_parser.add_argument(
        "--no-skip-processed",
        action="store_false",
        dest="skip_processed",
        help="모든 문서 재분류 (이미 처리된 문서도 다시 처리)",
    )

    monthly_parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="병렬 처리 활성화 (LangChain async, 기본: True)",
    )

    monthly_parser.add_argument(
        "--no-parallel",
        action="store_false",
        dest="parallel",
        help="순차 처리 (병렬 처리 비활성화)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "daily":
            run_daily_classification(args)
        elif args.command == "weekly":
            run_weekly_classification(args)
        elif args.command == "monthly":
            run_monthly_classification(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자에 의해 중단되었습니다.")


if __name__ == "__main__":
    main()
