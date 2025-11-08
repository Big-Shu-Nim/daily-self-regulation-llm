"""
Daily Feedback Prompts.

일일 피드백을 위한 시스템 프롬프트입니다.
기존 feedback_prompts.py의 프롬프트를 재사용할 수 있습니다.
"""

from llm_engineering.application.prompts.feedback_prompts import (
    SYSTEM_PROMPT_ORIGINAL,
    get_prompt,
)

# 기본 일일 피드백 프롬프트
DAILY_FEEDBACK_PROMPT = SYSTEM_PROMPT_ORIGINAL

__all__ = ["DAILY_FEEDBACK_PROMPT", "get_prompt"]
