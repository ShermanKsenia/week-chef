"""Tests for ``process_user_turn`` (mocked LLM / pipeline)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from weekchef.llm.errors import LLMUnavailableError
from weekchef.llm.generate_questions import questions_from_missing_fields_template
from weekchef.llm.outputs import ParseInputResult
from weekchef.orchestrator_turn import (
    ORCH_AWAITING_CLARIFICATION,
    ORCH_CLARIFICATION_ROUND,
    ORCH_INTAKE_DRAFT,
    ORCH_PENDING_USER_TEXT,
    process_user_turn,
)
from weekchef.schemas import PlanMeta, ValidatePlanResult, WeeklyPlan


def test_missing_fields_returns_questions_and_draft():
    conn = MagicMock()
    parsed = ParseInputResult(
        intent_summary="plan week",
        missing_required_fields=["servings"],
    )
    with (
        patch("weekchef.orchestrator_turn.load_or_seed_profile") as lp,
        patch("weekchef.orchestrator_turn.run_parse_input_sync", return_value=parsed),
        patch("weekchef.orchestrator_turn.run_weekly_plan_pipeline_with_shopping") as pipe,
    ):
        lp.return_value = MagicMock()
        resp = process_user_turn(conn, 42, "Plan my week", {})
    pipe.assert_not_called()
    assert resp.awaiting_clarification is True
    assert "servings" in resp.reply.lower() or "detail" in resp.reply.lower()
    assert ORCH_INTAKE_DRAFT in resp.session_patch
    assert resp.session_patch.get(ORCH_AWAITING_CLARIFICATION) is True
    assert resp.session_patch.get(ORCH_CLARIFICATION_ROUND) == 1
    assert resp.optional_plan is None


def test_max_clarification_rounds_stops():
    conn = MagicMock()
    parsed = ParseInputResult(missing_required_fields=["servings"])
    session = {
        ORCH_AWAITING_CLARIFICATION: True,
        ORCH_PENDING_USER_TEXT: "first",
        ORCH_CLARIFICATION_ROUND: 5,
    }
    with (
        patch("weekchef.orchestrator_turn.load_or_seed_profile") as lp,
        patch("weekchef.orchestrator_turn.run_parse_input_sync", return_value=parsed),
        patch("weekchef.orchestrator_turn.run_weekly_plan_pipeline_with_shopping") as pipe,
    ):
        lp.return_value = MagicMock()
        resp = process_user_turn(conn, 42, "still vague", session)
    pipe.assert_not_called()
    assert resp.awaiting_clarification is False
    assert "Too many" in resp.reply or "fresh" in resp.reply.lower()


def test_complete_intake_runs_pipeline(monkeypatch: pytest.MonkeyPatch):
    conn = MagicMock()
    parsed = ParseInputResult(intent_summary="ok", missing_required_fields=[])
    plan = WeeklyPlan(week_start="2026-04-13", days=[], meta=PlanMeta(pipeline_version="t"))
    pipe_result = MagicMock(
        plan=plan,
        validate_result=ValidatePlanResult(valid=True, reason_codes=[]),
        shopping=MagicMock(error=None, lines=[]),
        llm_unavailable=False,
    )

    profile = MagicMock()
    profile.user_id = "tg:42"
    profile.timezone = "UTC"

    with (
        patch("weekchef.orchestrator_turn.load_or_seed_profile", return_value=profile),
        patch("weekchef.orchestrator_turn.run_parse_input_sync", return_value=parsed),
        patch(
            "weekchef.orchestrator_turn.run_weekly_plan_pipeline_with_shopping",
            return_value=pipe_result,
        ),
        patch("weekchef.orchestrator_turn.apply_parse_overrides", return_value=profile),
        patch("weekchef.orchestrator_turn.get_settings") as gs,
        patch("weekchef.orchestrator_turn.cook_events_from_weekly_plan", return_value=[]),
    ):
        settings = MagicMock()
        settings.pipeline_version = "test"
        settings.google_calendar_enabled = False
        gs.return_value = settings
        resp = process_user_turn(conn, 42, "2 people, lunch and dinner", {})

    assert resp.optional_plan is plan
    assert resp.session_patch.get("last_plan") is not None
    assert resp.awaiting_clarification is False


def test_questions_template_lists_missing_field():
    p = ParseInputResult(missing_required_fields=["servings"])
    t = questions_from_missing_fields_template(p)
    assert "servings" in t.lower() or "how many" in t.lower()


def test_parse_llm_unavailable():
    conn = MagicMock()
    with patch("weekchef.orchestrator_turn.run_parse_input_sync", side_effect=LLMUnavailableError("x")):
        resp = process_user_turn(conn, 1, "hello", {})
    assert "unavailable" in resp.reply.lower()
