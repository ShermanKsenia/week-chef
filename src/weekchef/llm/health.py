"""Minimal LLM connectivity check (JSON ping)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from pydantic import BaseModel

from weekchef.config import get_settings
from weekchef.llm.client import build_sync_openai_client
from weekchef.llm.completions import complete_json_sync


class _HealthPayload(BaseModel):
    ok: bool = True


def llm_health_ping(*, settings: Any | None = None, client: Any | None = None) -> dict[str, Any]:
    """One structured JSON round-trip to verify API key, routing, and model."""
    s = settings or get_settings()
    c = client or build_sync_openai_client(s)
    messages = [
        {
            "role": "system",
            "content": "Reply with JSON only: {\"ok\": true}",
        },
        {"role": "user", "content": "ping"},
    ]
    out = complete_json_sync(
        messages,
        _HealthPayload,
        settings=s,
        client=c,
        temperature=0.0,
        max_tokens=32,
    )
    return {"ok": out.ok, "model": s.llm_model, "base_url": str(s.effective_llm_base_url())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM health: one JSON completion via configured model.")
    parser.parse_args(argv)
    try:
        payload = llm_health_ping()
    except Exception as e:  # noqa: BLE001
        err = {"ok": False, "error": str(e).replace("\n", " ")}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
