"""generate_questions — уточняющие вопросы при неполном INTAKE (PoC + опциональный LLM)."""

from __future__ import annotations

from typing import Any

from weekchef.config import Settings, get_settings
from weekchef.llm.completions import complete_json_sync
from weekchef.llm.errors import LLMInvalidResponseError, LLMUnavailableError
from weekchef.llm.outputs import GenerateQuestionsResult, ParseInputResult
from weekchef.llm.prompts import GENERATE_QUESTIONS_SYSTEM, GENERATE_QUESTIONS_VERSION

_FIELD_HINTS: dict[str, str] = {
    "servings": "How many servings should most meals be planned for?",
    "meals_per_day": "How many cooked meals per day do you want in the plan?",
    "week_start_iso": "Which week should we plan (week start date, YYYY-MM-DD)?",
    "restrictions": "Any allergies or ingredients to avoid?",
    "goal": "What is your main goal for this week (e.g. budget, protein, variety)?",
}


def questions_from_missing_fields_template(parsed: ParseInputResult) -> str:
    """Deterministic PoC: one short question per missing field name."""
    fields = list(parsed.missing_required_fields or [])
    if not fields:
        return "What else should we know before planning your week?"
    lines: list[str] = []
    for name in fields:
        hint = _FIELD_HINTS.get(name.strip().lower(), None)
        if hint:
            lines.append(f"- {hint}")
        else:
            lines.append(f"- Please clarify: {name}")
    intro = "To build your plan, I need a bit more detail:\n"
    return intro + "\n".join(lines)


def run_generate_questions_sync(
    parsed: ParseInputResult,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    use_llm: bool = False,
) -> str:
    """
    Return user-facing clarification text.

    When ``use_llm`` is True, asks the model for phrasing; on failure falls back to the template.
    """
    if not use_llm:
        return questions_from_missing_fields_template(parsed)
    s = settings or get_settings()
    payload = parsed.model_dump_json()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": GENERATE_QUESTIONS_SYSTEM},
        {
            "role": "user",
            "content": f"Parse result JSON:\n{payload}\n\nProduce friendly follow-up questions.",
        },
    ]
    try:
        out = complete_json_sync(
            messages,
            GenerateQuestionsResult,
            settings=s,
            client=client,
            temperature=0.3,
            max_tokens=500,
            llm_step="generate_questions",
            prompt_version=GENERATE_QUESTIONS_VERSION,
        )
        text = (out.assistant_reply or "").strip()
        if text:
            return text
    except (LLMUnavailableError, LLMInvalidResponseError, ValueError):
        pass
    return questions_from_missing_fields_template(parsed)
