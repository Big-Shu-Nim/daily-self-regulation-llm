"""
Weekly Feedback Generator.

7일간의 데이터를 분석하여 주간 피드백을 생성합니다.
"""

from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import Optional

from langchain.prompts import ChatPromptTemplate
from langchain_core.tracers.context import tracing_v2_enabled
from loguru import logger

from llm_engineering.domain.feedback_documents import WeeklyFeedbackDocument
from llm_engineering.settings import Settings
from ..base import BaseFeedbackGenerator
from ..document_loader import DocumentLoader
from .prompts import WEEKLY_FEEDBACK_PROMPT, WEEKLY_FEEDBACK_PROMPT_V2, get_weekly_prompt

# Load settings singleton
settings = Settings.load_settings()


class WeeklyFeedbackGenerator(BaseFeedbackGenerator):
    """
    주간 피드백 생성기.

    특징:
    - 7일간의 모든 데이터 in-context 로드
    - 과거 주간 리포트 참조 (Notion)
    - 패턴 분석 중심
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        prompt_style: str = "original",
    ):
        """
        Initialize the weekly feedback generator.

        Args:
            model_id: LLM model ID
            temperature: LLM temperature
            prompt_style: 프롬프트 스타일 ("original", "v2", "v3")
        """
        super().__init__(model_id, temperature)
        self.prompt_style = prompt_style
        # V3는 두 단계로 나뉘므로 초기 프롬프트는 필요 없음
        if prompt_style != "v3":
            self.system_prompt = get_weekly_prompt(prompt_style)

        logger.info(f"WeeklyFeedbackGenerator initialized (style={prompt_style})")

    def generate(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        author_full_name: Optional[str] = None,
        include_past_reports: bool = True,
        past_reports_limit: int = 4,
        additional_context: Optional[str] = None,
        precomputed_metrics: Optional[dict] = None,
        save_to_db: bool = False,
    ) -> str:
        """
        주간 피드백을 생성합니다.

        Args:
            start_date: 주 시작 날짜 (YYYY-MM-DD, 월요일 권장)
            end_date: 주 종료 날짜 (YYYY-MM-DD, 선택사항, 기본: start_date + 6일)
            author_full_name: 작성자 이름 (선택사항)
            include_past_reports: 과거 주간 리포트 포함 여부
            past_reports_limit: 과거 주간 리포트 최대 개수
            additional_context: 추가 컨텍스트 (선택사항)
            precomputed_metrics: 사전 계산된 메트릭 (V2 프롬프트용)

        Returns:
            생성된 주간 피드백 문자열
        """
        # 종료일 계산
        if end_date is None:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=6)
            end_date = end_dt.strftime("%Y-%m-%d")

        logger.info(f"Generating weekly feedback for {start_date} ~ {end_date} (style={self.prompt_style})")

        # 1. 7일 데이터 로드
        weekly_docs = DocumentLoader.load_by_date_range(
            start_date=start_date,
            end_date=end_date,
            sources=["calendar", "notion", "naver_blog"],
            author_full_name=author_full_name,
            include_weekly_reports=False,  # 이번 주 리포트는 제외
        )

        # 2. 과거 주간 리포트 로드 (컨텍스트용)
        past_reports = []
        if include_past_reports:
            past_reports = DocumentLoader.load_weekly_reports(
                start_date=self._get_past_week_start(start_date, weeks_back=8),
                end_date=start_date,  # 이번 주 시작 전까지
                author_full_name=author_full_name,
                limit=past_reports_limit,
            )

        # 3. 통계 로깅
        self._log_statistics(start_date, end_date, weekly_docs, past_reports)

        # 4. 프롬프트 스타일에 따른 처리
        try:
            # LangSmith 추적 활성화
            if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
                import os
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT

            if self.prompt_style == "v3":
                # V3: 2단계 체인 (JSON → Report)
                if not precomputed_metrics:
                    raise ValueError("V3 스타일은 precomputed_metrics가 필수입니다")

                feedback = self._generate_v3_two_step(
                    start_date, end_date, weekly_docs, past_reports, precomputed_metrics
                )
            elif self.prompt_style in ["v2", "v2_public"] and precomputed_metrics:
                # V2/V2_PUBLIC: 사전 계산된 메트릭 사용 - ChatPromptTemplate 우회 (JSON 중괄호 충돌 방지)
                from langchain_core.messages import HumanMessage
                formatted_prompt = self._format_v2_context(
                    start_date, end_date, weekly_docs, past_reports, precomputed_metrics
                )
                response = self.llm.invoke([HumanMessage(content=formatted_prompt)])
                feedback = response.content
            else:
                # Original/Public: 기존 방식
                context = self._format_weekly_context(
                    start_date, end_date, weekly_docs, past_reports
                )
                if additional_context:
                    context += f"\n\n## 추가 컨텍스트\n{additional_context}"
                prompt = ChatPromptTemplate.from_messages(
                    [("system", self.system_prompt), ("human", "{context}")]
                )
                chain = prompt | self.llm
                response = chain.invoke({"context": context})
                feedback = response.content

            logger.info(
                f"Weekly feedback generated successfully ({len(feedback)} chars)"
            )
            return feedback

        except Exception as e:
            logger.error(f"Error generating weekly feedback: {e}")
            raise

    def _format_v2_context(
        self,
        start_date: str,
        end_date: str,
        weekly_docs: list[dict],
        past_reports: list[dict],
        precomputed_metrics: dict,
    ) -> str:
        """
        V2 프롬프트용 컨텍스트를 포맷팅합니다.
        사전 계산된 메트릭을 포함합니다.

        Args:
            start_date: 주 시작 날짜
            end_date: 주 종료 날짜
            weekly_docs: 이번 주 데이터
            past_reports: 과거 주간 리포트
            precomputed_metrics: 사전 계산된 메트릭

        Returns:
            포맷팅된 V2 컨텍스트 문자열
        """
        import json

        # 메트릭 포맷팅
        metrics_str = json.dumps(precomputed_metrics, ensure_ascii=False, indent=2)

        # Raw logs 포맷팅 (간략화)
        raw_logs_parts = []
        if weekly_docs:
            docs_by_date = self._group_by_date(weekly_docs)
            for date in sorted(docs_by_date.keys()):
                day_docs = docs_by_date[date]
                day_name = self._get_day_name(date)
                raw_logs_parts.append(f"### {date} ({day_name})")
                for doc in day_docs:
                    raw_logs_parts.append(self._format_document(doc))
                raw_logs_parts.append("")
        raw_logs_str = "\n".join(raw_logs_parts) if raw_logs_parts else "데이터 없음"

        # 이전 주 요약
        prev_summary_parts = []
        if past_reports:
            # 가장 최근 1개만 사용
            latest_report = past_reports[0]
            week_start = latest_report.get("metadata", {}).get("week_start_date", "N/A")
            week_end = latest_report.get("metadata", {}).get("week_end_date", "N/A")
            prev_summary_parts.append(f"### 지난 주: {week_start} ~ {week_end}")
            prev_summary_parts.append(latest_report.get("content", "")[:2000])  # 최대 2000자
        prev_summary_str = "\n".join(prev_summary_parts) if prev_summary_parts else "없음"

        # V2 프롬프트에 값 채우기
        formatted_prompt = self.system_prompt.format(
            start_date=start_date,
            end_date=end_date,
            precomputed_metrics=metrics_str,
            raw_logs=raw_logs_str,
            previous_week_summary=prev_summary_str,
        )

        return formatted_prompt

    def _format_weekly_context(
        self,
        start_date: str,
        end_date: str,
        weekly_docs: list[dict],
        past_reports: list[dict],
    ) -> str:
        """
        주간 데이터를 LLM 입력 형식으로 포맷팅합니다.

        Args:
            start_date: 주 시작 날짜
            end_date: 주 종료 날짜
            weekly_docs: 이번 주 7일 데이터
            past_reports: 과거 주간 리포트

        Returns:
            포맷팅된 컨텍스트 문자열
        """
        context_parts = []

        # 주간 정보
        context_parts.append(f"## 주간 분석 대상: {start_date} ~ {end_date}")
        context_parts.append("")

        # 이번 주 데이터
        if weekly_docs:
            # 날짜별로 그룹화
            docs_by_date = self._group_by_date(weekly_docs)

            context_parts.append("## 이번 주 데이터 (일별)")
            context_parts.append("")

            for date in sorted(docs_by_date.keys()):
                day_docs = docs_by_date[date]
                day_name = self._get_day_name(date)

                context_parts.append(f"### {date} ({day_name})")
                context_parts.append("")

                for doc in day_docs:
                    context_parts.append(self._format_document(doc))
                    context_parts.append("")
        else:
            context_parts.append("## 이번 주 데이터")
            context_parts.append("")
            context_parts.append("해당 기간의 데이터를 찾을 수 없습니다.")
            context_parts.append("")

        # 과거 주간 리포트
        if past_reports:
            context_parts.append("## 과거 주간 리포트 (참고용)")
            context_parts.append("")

            for report in past_reports:
                week_start = report.get("metadata", {}).get("week_start_date", "N/A")
                week_end = report.get("metadata", {}).get("week_end_date", "N/A")
                title = report.get("metadata", {}).get("title", "주간 리포트")

                context_parts.append(f"### {title} ({week_start} ~ {week_end})")
                context_parts.append("")
                context_parts.append(report.get("content", ""))
                context_parts.append("")
                context_parts.append("---")
                context_parts.append("")

        return "\n".join(context_parts)

    def _group_by_date(self, docs: list[dict]) -> dict[str, list[dict]]:
        """
        문서를 ref_date 기준으로 그룹화합니다.

        Args:
            docs: 문서 리스트

        Returns:
            날짜별 문서 딕셔너리
        """
        grouped = {}
        for doc in docs:
            ref_date = doc.get("ref_date", "unknown")
            if ref_date not in grouped:
                grouped[ref_date] = []
            grouped[ref_date].append(doc)
        return grouped

    def _get_day_name(self, date_str: str) -> str:
        """
        날짜 문자열을 요일명으로 변환합니다.

        Args:
            date_str: YYYY-MM-DD 형식 날짜

        Returns:
            요일명 (예: "월요일")
        """
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
            return days[date_obj.weekday()]
        except Exception:
            return ""

    def _get_past_week_start(self, current_week_start: str, weeks_back: int = 8) -> str:
        """
        과거 N주 전의 시작 날짜를 계산합니다.

        Args:
            current_week_start: 현재 주 시작 날짜
            weeks_back: 몇 주 전부터

        Returns:
            과거 주 시작 날짜 (YYYY-MM-DD)
        """
        date_obj = datetime.strptime(current_week_start, "%Y-%m-%d")
        past_date = date_obj - timedelta(weeks=weeks_back)
        return past_date.strftime("%Y-%m-%d")

    def _log_statistics(
        self,
        start_date: str,
        end_date: str,
        weekly_docs: list[dict],
        past_reports: list[dict],
    ):
        """
        로드된 문서 통계를 로깅합니다.

        Args:
            start_date: 주 시작 날짜
            end_date: 주 종료 날짜
            weekly_docs: 주간 문서 리스트
            past_reports: 과거 주간 리포트 리스트
        """
        stats = {
            "week": f"{start_date} ~ {end_date}",
            "total_docs": len(weekly_docs),
            "past_reports": len(past_reports),
        }

        # 플랫폼별 통계
        if weekly_docs:
            stats["by_platform"] = self._count_documents(weekly_docs)

        # 날짜별 통계
        docs_by_date = self._group_by_date(weekly_docs)
        stats["by_date"] = {date: len(docs) for date, docs in docs_by_date.items()}

        logger.info(f"Weekly statistics: {stats}")

    def _generate_v3_two_step(
        self,
        start_date: str,
        end_date: str,
        weekly_docs: list[dict],
        past_reports: list[dict],
        precomputed_metrics: dict,
    ) -> str:
        """
        V3 스타일: 2단계 체인으로 피드백 생성.

        Step 1: JSON Summary 생성
        Step 2: JSON을 기반으로 서술형 리포트 생성

        Args:
            start_date: 주 시작 날짜
            end_date: 주 종료 날짜
            weekly_docs: 이번 주 데이터
            past_reports: 과거 주간 리포트
            precomputed_metrics: 사전 계산된 메트릭

        Returns:
            서술형 리포트 + JSON 조합 문자열
        """
        import json
        import re
        from langchain_core.messages import HumanMessage

        logger.info("V3: Starting Step 1 - Generating JSON summary")

        # Step 1: JSON 생성
        step1_prompt = get_weekly_prompt("v3_step1")
        step1_formatted = self._format_v3_step1_context(
            start_date, end_date, weekly_docs, past_reports, precomputed_metrics, step1_prompt
        )
        step1_response = self.llm.invoke([HumanMessage(content=step1_formatted)])
        json_text = step1_response.content

        logger.info(f"V3 Step 1 completed ({len(json_text)} chars)")

        # JSON 파싱 (```json ... ``` 블록 또는 순수 JSON 추출)
        json_summary = self._extract_json(json_text)

        if not json_summary:
            logger.error("Failed to extract valid JSON from Step 1")
            raise ValueError("Step 1에서 유효한 JSON을 추출하지 못했습니다")

        logger.info("V3: Starting Step 2 - Generating report from JSON")

        # Step 2: 리포트 생성
        step2_prompt = get_weekly_prompt("v3_step2")
        step2_formatted = step2_prompt.format(
            json_summary=json_summary,
            start_date=start_date,
            end_date=end_date,
        )
        step2_response = self.llm.invoke([HumanMessage(content=step2_formatted)])
        report_text = step2_response.content

        logger.info(f"V3 Step 2 completed ({len(report_text)} chars)")

        # JSON을 로그에만 남기고, 사용자에게는 리포트만 반환
        logger.debug(f"Step 1 JSON Summary:\n{json_summary}")

        # 최종 결과: 리포트만 (JSON은 LangSmith에서 확인 가능)
        return report_text

    def _format_v3_step1_context(
        self,
        start_date: str,
        end_date: str,
        weekly_docs: list[dict],
        past_reports: list[dict],
        precomputed_metrics: dict,
        prompt_template: str,
    ) -> str:
        """
        V3 Step 1 프롬프트용 컨텍스트를 포맷팅합니다.

        Args:
            start_date: 주 시작 날짜
            end_date: 주 종료 날짜
            weekly_docs: 이번 주 데이터
            past_reports: 과거 주간 리포트
            precomputed_metrics: 사전 계산된 메트릭
            prompt_template: Step 1 프롬프트 템플릿

        Returns:
            포맷팅된 프롬프트 문자열
        """
        import json

        # 메트릭 포맷팅
        metrics_str = json.dumps(precomputed_metrics, ensure_ascii=False, indent=2)

        # Raw logs 포맷팅 (간략화)
        raw_logs_parts = []
        if weekly_docs:
            docs_by_date = self._group_by_date(weekly_docs)
            for date in sorted(docs_by_date.keys()):
                day_docs = docs_by_date[date]
                day_name = self._get_day_name(date)
                raw_logs_parts.append(f"### {date} ({day_name})")
                for doc in day_docs:
                    raw_logs_parts.append(self._format_document(doc))
                raw_logs_parts.append("")
        raw_logs_str = "\n".join(raw_logs_parts) if raw_logs_parts else "데이터 없음"

        # 이전 주 요약
        prev_summary_parts = []
        if past_reports:
            # 가장 최근 1개만 사용
            latest_report = past_reports[0]
            week_start = latest_report.get("metadata", {}).get("week_start_date", "N/A")
            week_end = latest_report.get("metadata", {}).get("week_end_date", "N/A")
            prev_summary_parts.append(f"### 지난 주: {week_start} ~ {week_end}")
            prev_summary_parts.append(latest_report.get("content", "")[:2000])  # 최대 2000자
        prev_summary_str = "\n".join(prev_summary_parts) if prev_summary_parts else "없음"

        # 프롬프트에 값 채우기
        formatted_prompt = prompt_template.format(
            start_date=start_date,
            end_date=end_date,
            precomputed_metrics=metrics_str,
            raw_logs=raw_logs_str,
            previous_week_summary=prev_summary_str,
        )

        return formatted_prompt

    def _extract_json(self, text: str) -> str:
        """
        텍스트에서 JSON을 추출합니다.

        ```json ... ``` 블록이나 순수 JSON을 찾아 파싱 검증합니다.

        Args:
            text: JSON을 포함한 텍스트

        Returns:
            추출된 JSON 문자열 (파싱 검증됨) 또는 빈 문자열
        """
        import json
        import re

        logger.debug(f"Extracting JSON from text (length: {len(text)})")

        # 1. ```json ... ``` 블록 찾기 (가장 일반적)
        json_block_pattern = r"```json\s*(.*?)\s*```"
        matches = re.findall(json_block_pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            logger.debug(f"Found {len(matches)} ```json...``` blocks")
            for i, match in enumerate(matches):
                try:
                    # 파싱 검증
                    json.loads(match)
                    logger.info(f"Successfully extracted JSON from ```json``` block #{i+1}")
                    return match.strip()
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON block #{i+1} parse failed: {e}")
                    continue

        # 2. ``` ... ``` 블록 찾기 (json 키워드 없이)
        code_block_pattern = r"```\s*(.*?)\s*```"
        matches = re.findall(code_block_pattern, text, re.DOTALL)
        if matches:
            logger.debug(f"Found {len(matches)} ``` ... ``` blocks (no json keyword)")
            for i, match in enumerate(matches):
                # { 로 시작하는 경우만 시도
                if match.strip().startswith("{"):
                    try:
                        json.loads(match)
                        logger.info(f"Successfully extracted JSON from code block #{i+1}")
                        return match.strip()
                    except json.JSONDecodeError:
                        continue

        # 3. 순수 JSON 찾기 (중괄호로 시작)
        # 첫 번째 { 부터 마지막 } 까지
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                json.loads(candidate)
                logger.info("Successfully extracted JSON from raw text (first { to last })")
                return candidate.strip()
            except json.JSONDecodeError as e:
                logger.warning(f"Raw JSON extraction failed: {e}")

        # 4. 마지막 시도: 줄 단위로 { 찾아서 끝까지
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                # 이 줄부터 끝까지 합쳐서 시도
                candidate = "\n".join(lines[i:])
                # 마지막 } 찾기
                last_brace_idx = candidate.rfind("}")
                if last_brace_idx != -1:
                    candidate = candidate[: last_brace_idx + 1]
                    try:
                        json.loads(candidate)
                        logger.info(f"Successfully extracted JSON starting from line {i+1}")
                        return candidate.strip()
                    except json.JSONDecodeError:
                        continue

        logger.error("Failed to extract valid JSON from text")
        logger.debug(f"Text preview (first 500 chars): {text[:500]}")
        return ""

    @staticmethod
    def remove_json_section(text: str) -> str:
        """
        피드백 텍스트에서 JSON 섹션을 제거합니다.

        V2 프롬프트는 리포트 + JSON을 모두 출력하므로,
        대시보드에서 사람이 읽을 때는 JSON 부분을 제거합니다.

        Args:
            text: 피드백 전체 텍스트 (리포트 + JSON 포함 가능)

        Returns:
            JSON 섹션이 제거된 텍스트 (리포트만)
        """
        import re

        # 패턴 1: JSON SUMMARY 섹션 제거
        # 다양한 형식 지원: "OUTPUT — B)", ":B)", "B) JSON", "## JSON" 등
        patterns = [
            r"OUTPUT\s*[—-]\s*B\).*?$",  # "OUTPUT — B) JSON SUMMARY" 이후 모두 제거
            r"----+\s*OUTPUT\s*[—-]\s*B\).*?$",  # "---- OUTPUT — B)" 이후 모두 제거
            r"---+\s*##\s*JSON Summary.*?$",  # "--- ## JSON Summary" 이후 모두 제거
            r":?B\)\s*JSON\s*SUMMARY.*?$",  # ":B) JSON SUMMARY" 또는 "B) JSON SUMMARY" 이후 모두 제거
            r"##\s*JSON\s*SUMMARY.*?$",  # "## JSON SUMMARY" 이후 모두 제거
            r"----+\s*$",  # "----" 이후 모두 제거 (JSON이 구분선 뒤에 오는 경우)
        ]

        result = text
        for pattern in patterns:
            result = re.sub(pattern, "", result, flags=re.DOTALL | re.IGNORECASE)

        # 패턴 2: ```json ... ``` 블록 제거
        result = re.sub(r"```json\s*.*?\s*```", "", result, flags=re.DOTALL | re.IGNORECASE)

        # 패턴 3: 단독 { ... } JSON 블록 제거 (마지막 부분에 있는 경우)
        # 마지막 200자 정도에서 { 로 시작하는 JSON이 있으면 제거
        lines = result.strip().split("\n")
        # 끝에서부터 역순으로 확인
        for i in range(len(lines) - 1, max(0, len(lines) - 50), -1):
            if lines[i].strip().startswith("{"):
                # 여기부터 끝까지가 JSON일 가능성
                potential_json = "\n".join(lines[i:])
                try:
                    import json
                    json.loads(potential_json)
                    # 유효한 JSON이면 제거
                    result = "\n".join(lines[:i])
                    logger.debug(f"Removed trailing JSON block starting at line {i+1}")
                    break
                except json.JSONDecodeError:
                    continue

        return result.strip()
