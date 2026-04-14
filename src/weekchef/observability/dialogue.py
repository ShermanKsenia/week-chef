"""Dialogue identity persisted in session (multi-turn traces)."""

from __future__ import annotations

import uuid
from typing import Any

OBS_DIALOGUE_ID = "obs_dialogue_id"
OBS_TURN_INDEX = "obs_turn_index"


def prepare_turn_patch(session: dict[str, Any]) -> dict[str, Any]:
    """Assign ``obs_dialogue_id`` on first turn; increment ``obs_turn_index`` each message."""
    did = session.get(OBS_DIALOGUE_ID)
    if not did or not isinstance(did, str):
        did = str(uuid.uuid4())
    turn = int(session.get(OBS_TURN_INDEX) or 0) + 1
    return {OBS_DIALOGUE_ID: did, OBS_TURN_INDEX: turn}


def reset_dialogue_state() -> dict[str, Any]:
    """Clear dialogue after a successful plan (new conversation)."""
    return {OBS_DIALOGUE_ID: None, OBS_TURN_INDEX: 0}
