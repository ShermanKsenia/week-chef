"""LLM access via OpenAI SDK (OpenRouter-compatible)."""

from weekchef.llm.client import (
    build_async_openai_client,
    build_sync_openai_client,
    effective_llm_base_url,
)
from weekchef.llm.completions import complete_json_async, complete_json_sync
from weekchef.llm.errors import LLMUnavailableError
from weekchef.llm.generate_questions import run_generate_questions_sync
from weekchef.llm.outputs import GenerateQuestionsResult, MealPickResult, ParseInputResult
from weekchef.llm.parse_input import run_parse_input_sync

__all__ = [
    "GenerateQuestionsResult",
    "LLMUnavailableError",
    "MealPickResult",
    "ParseInputResult",
    "build_async_openai_client",
    "build_sync_openai_client",
    "complete_json_async",
    "complete_json_sync",
    "effective_llm_base_url",
    "run_generate_questions_sync",
    "run_parse_input_sync",
]
