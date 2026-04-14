"""Week Chef — minimal chat UI calling ``process_user_turn`` (orchestrator facade only)."""

from __future__ import annotations

import json
import random
import sys
import uuid
from pathlib import Path

# Allow `streamlit run streamlit_app.py` from repo root without editable install.
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st

from weekchef.config import get_settings
from weekchef.db.pool import sync_connection
from weekchef.db.sessions import session_get, session_upsert
from weekchef.observability import configure_observability, prepare_turn_patch, request_context
from weekchef.observability.dialogue import OBS_DIALOGUE_ID, OBS_TURN_INDEX
from weekchef.orchestrator_turn import process_user_turn
from weekchef.planning_commands import merge_session_state
from weekchef.profile import telegram_user_key

st.set_page_config(page_title="Week Chef", page_icon="🍳", layout="centered")

_settings = get_settings()
if "_wc_obs_initialized" not in st.session_state:
    configure_observability(_settings)
    st.session_state._wc_obs_initialized = True

st.title("Week Chef")
st.caption(
    "Natural-language chat uses the orchestrator (`process_user_turn`): "
    "intake, optional clarification questions, then weekly plan + shopping when valid."
)

if "wc_client_id" not in st.session_state:
    st.session_state.wc_client_id = random.randrange(1, 2**31 - 1)
if "messages" not in st.session_state:
    st.session_state.messages = []


def _render_history() -> None:
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            pj = msg.get("plan_json")
            if pj:
                with st.expander("plan.json"):
                    st.code(pj[:12000], language="json")
                st.download_button(
                    "Download plan.json",
                    data=pj.encode("utf-8"),
                    file_name="plan.json",
                    mime="application/json",
                    key=f"dl_{i}",
                )


_render_history()

user_text = st.chat_input("Describe what you want for the week…")
if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})

    client_id = int(st.session_state.wc_client_id)
    assistant_msg: str
    plan_json: str | None = None

    try:
        settings = _settings
        correlation_id = str(uuid.uuid4())
        with st.spinner("Orchestrator is working…"):
            with sync_connection(settings.database_url) as conn:
                st_db = session_get(conn, client_id)
                obs_patch = prepare_turn_patch(st_db)
                st2 = merge_session_state(st_db, obs_patch)
                if client_id:
                    session_upsert(conn, client_id, st2)
                uk = telegram_user_key(client_id)
                with request_context(
                    correlation_id=correlation_id,
                    user_key=uk,
                    dialogue_id=str(st2.get(OBS_DIALOGUE_ID) or ""),
                    turn_index=int(st2.get(OBS_TURN_INDEX) or 0),
                ):
                    resp = process_user_turn(conn, client_id, user_text, st2)
                    merged = merge_session_state(st2, resp.session_patch)
                    if client_id:
                        session_upsert(conn, client_id, merged)
                assistant_msg = resp.reply
                if resp.optional_plan is not None:
                    plan_json = json.dumps(
                        json.loads(resp.optional_plan.model_dump_json()),
                        indent=2,
                        ensure_ascii=False,
                    )
    except Exception as e:  # noqa: BLE001
        assistant_msg = f"Something went wrong: {e}"

    entry: dict = {"role": "assistant", "content": assistant_msg}
    if plan_json:
        entry["plan_json"] = plan_json
    st.session_state.messages.append(entry)
    # History was drawn above before these appends; rerun so user + assistant render.
    st.rerun()
