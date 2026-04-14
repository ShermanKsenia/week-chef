"""Single user-turn facade: INTAKE → (questions | weekly pipeline + shopping)."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

from psycopg import Connection
from pydantic import BaseModel, Field

from weekchef.config import Settings, get_settings
from weekchef.llm.completions import llm_unavailable_after_schema_retries
from weekchef.llm.langfuse_util import flush_langfuse
from weekchef.llm.errors import LLMUnavailableError
from weekchef.llm.generate_questions import run_generate_questions_sync
from weekchef.llm.outputs import ParseInputResult
from weekchef.llm.parse_input import run_parse_input_sync
from weekchef.observability import get_logger, intake_text_hash
from weekchef.observability.dialogue import reset_dialogue_state
from weekchef.observability.spans import user_turn_root_span
from weekchef.orchestrator_pipeline import apply_parse_overrides, run_weekly_plan_pipeline_with_shopping
from weekchef.profile import load_or_seed_profile, telegram_user_key
from weekchef.schemas import WeeklyPlan
from weekchef.tools.calendar import cook_events_from_weekly_plan

# Session keys (merge via session_patch into persisted JSON state).
ORCH_INTAKE_DRAFT = "orch_intake_draft"
ORCH_AWAITING_CLARIFICATION = "orch_awaiting_clarification"
ORCH_CLARIFICATION_ROUND = "orch_clarification_round"
ORCH_PENDING_USER_TEXT = "orch_pending_user_text"

_MAX_CLARIFICATION_ROUNDS = 5

log = get_logger("weekchef.orchestrator_turn")


def _profile_path() -> Path:
    raw = os.environ.get("WEEKCHEF_PROFILE_PATH", "fixtures/profile.json")
    return Path(raw)


def _format_shopping_text(shop: Any) -> str | None:
    if shop is None:
        return None
    if getattr(shop, "error", None):
        return f"Shopping list failed: {shop.error}"
    lines_out = getattr(shop, "lines", None) or []
    if not lines_out:
        return "Shopping list is empty."
    lines: list[str] = []
    for ln in lines_out:
        tag = " (have)" if getattr(ln, "already_have", False) else ""
        q = f"{ln.qty:g} {ln.unit}".strip() if getattr(ln, "qty", None) is not None else (ln.unit or "")
        lines.append(f"- {ln.product}: {q}{tag}".strip())
    return "Shopping list:\n" + "\n".join(lines)


def _clear_orch_intake_keys() -> dict[str, Any]:
    return {
        ORCH_INTAKE_DRAFT: None,
        ORCH_AWAITING_CLARIFICATION: False,
        ORCH_CLARIFICATION_ROUND: 0,
        ORCH_PENDING_USER_TEXT: None,
    }


class UserTurnResponse(BaseModel):
    """One product-level turn: assistant text, optional artifacts, session delta."""

    reply: str
    optional_plan: WeeklyPlan | None = None
    shopping_text: str | None = None
    session_patch: dict[str, Any] = Field(default_factory=dict)
    awaiting_clarification: bool = False


def process_user_turn(
    conn: Connection,
    client_id: int,
    text: str,
    session: dict[str, Any],
    *,
    settings: Settings | None = None,
    rng: random.Random | None = None,
    client: Any | None = None,
    use_llm_for_questions: bool = False,
) -> UserTurnResponse:
    """
    INTAKE (``parse_input``) → if required fields missing, ``generate_questions`` and stop;
    else ENRICH → PLAN → … via ``run_weekly_plan_pipeline_with_shopping``.

    ``client_id`` is the Telegram numeric id (same namespace as ``weekchef_sessions``).

    ``session`` is the caller's view of persisted state; returned ``session_patch`` should be
    merged by the API layer (e.g. Telegram ``session_upsert``).
    """
    s = settings or get_settings()
    rng = rng or random.Random()
    raw = (text or "").strip()
    if not raw:
        return UserTurnResponse(reply="Send a short message describing what you want for the week.")

    awaiting = bool(session.get(ORCH_AWAITING_CLARIFICATION))
    pending = (session.get(ORCH_PENDING_USER_TEXT) or "").strip()
    intake_text = raw
    if awaiting and pending:
        intake_text = f"{pending}\n\n(Additional details from user: {raw})"

    with user_turn_root_span():
        try:
            log.info(
                "user_turn_start",
                intake_sha=intake_text_hash(intake_text),
                awaiting_clarification=awaiting,
            )
            try:
                parsed = run_parse_input_sync(intake_text, settings=s, client=client)
            except LLMUnavailableError as e:
                if llm_unavailable_after_schema_retries(e):
                    log.info(
                        "user_turn_intake_schema_retries_exhausted",
                        cause_types=[type(c).__name__ for c in (e.causes or [])][:8],
                    )
                    return UserTurnResponse(
                        reply=(
                            "We couldn't parse your reply into the expected intake format after several tries. "
                            "Try a shorter answer, or start over with one clear sentence about the week you want."
                        ),
                        session_patch={},
                    )
                log.info("user_turn_intake_llm_unavailable")
                return UserTurnResponse(
                    reply="The planner intake service is temporarily unavailable (LLM). Try again later.",
                    session_patch={},
                )

            missing = [m for m in (parsed.missing_required_fields or []) if str(m).strip()]
            if missing:
                round_prev = int(session.get(ORCH_CLARIFICATION_ROUND) or 0)
                next_round = round_prev + 1
                if next_round > _MAX_CLARIFICATION_ROUNDS:
                    patch = {
                        **_clear_orch_intake_keys(),
                        **reset_dialogue_state(),
                    }
                    log.info("user_turn_clarification_max_rounds")
                    return UserTurnResponse(
                        reply="Too many clarification rounds for this session. Describe your weekly meal request again from the start.",
                        session_patch=patch,
                        awaiting_clarification=False,
                    )
                q_text = run_generate_questions_sync(
                    parsed,
                    settings=s,
                    client=client,
                    use_llm=use_llm_for_questions,
                )
                base_pending = pending if awaiting else raw
                patch = {
                    ORCH_INTAKE_DRAFT: parsed.model_dump(),
                    ORCH_AWAITING_CLARIFICATION: True,
                    ORCH_CLARIFICATION_ROUND: next_round,
                    ORCH_PENDING_USER_TEXT: base_pending if base_pending else intake_text,
                }
                log.info("user_turn_clarification", missing_count=len(missing))
                return UserTurnResponse(
                    reply=q_text,
                    session_patch=patch,
                    awaiting_clarification=True,
                )

            user_key = telegram_user_key(client_id)
            profile = load_or_seed_profile(conn, user_key, _profile_path())
            working = apply_parse_overrides(profile, parsed)

            pipe = run_weekly_plan_pipeline_with_shopping(
                conn,
                working,
                s,
                intake_user_message=None,
                rng=rng,
                client=client,
            )

            if pipe.llm_unavailable:
                log.info("user_turn_pipeline_llm_unavailable")
                return UserTurnResponse(
                    reply="Planning is temporarily unavailable (LLM). Try again later or ask an admin to enable deterministic fallback.",
                    session_patch={**_clear_orch_intake_keys(), **reset_dialogue_state()},
                )

            plan = pipe.plan
            valid = pipe.validate_result.valid
            shop_txt = _format_shopping_text(pipe.shopping) if valid else None

            state: dict[str, Any] = {
                **_clear_orch_intake_keys(),
                **reset_dialogue_state(),
                "last_plan_valid": valid,
                "pipeline": s.pipeline_version,
                "last_plan": json.loads(plan.model_dump_json()),
            }
            if s.google_calendar_enabled:
                state["pending_calendar_events"] = cook_events_from_weekly_plan(plan)
            else:
                state["pending_calendar_events"] = []

            reason_tail = ""
            if plan.meta.reason_codes:
                reason_tail = " Notes: " + "; ".join(plan.meta.reason_codes[:5])
            reply = (
                f"Weekly plan built (valid={valid}).{reason_tail}"
                if valid
                else f"Plan built but validation reported issues (valid={valid}).{reason_tail}"
            )
            if valid and shop_txt:
                reply = reply + "\n\n" + shop_txt

            log.info(
                "user_turn_plan_done",
                plan_valid=valid,
                fallback_used=pipe.fallback_used,
                phases=pipe.phases_completed,
            )
            return UserTurnResponse(
                reply=reply,
                optional_plan=plan,
                shopping_text=shop_txt,
                session_patch=state,
                awaiting_clarification=False,
            )
        finally:
            flush_langfuse(s)
