"""parse_input — structured INTAKE from free text."""

from __future__ import annotations

from typing import Any

from weekchef.config import Settings, get_settings
from weekchef.llm.completions import complete_json_sync
from weekchef.llm.outputs import ParseInputResult
from weekchef.llm.prompts import PARSE_INPUT_SYSTEM, PARSE_INPUT_VERSION


def run_parse_input_sync(
    user_text: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> ParseInputResult:
    """Call the LLM and return validated ``ParseInputResult``."""
    s = settings or get_settings()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": PARSE_INPUT_SYSTEM},
        {"role": "user", "content": user_text.strip()},
    ]
    return complete_json_sync(
        messages,
        ParseInputResult,
        settings=s,
        client=client,
        temperature=0.1,
        max_tokens=1200,
        llm_step="parse_input",
        prompt_version=PARSE_INPUT_VERSION,
    )
