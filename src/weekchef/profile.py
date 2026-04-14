"""Load and validate user profile JSON."""

from __future__ import annotations

import json
from pathlib import Path

from weekchef.schemas import UserProfile


def load_profile(path: Path) -> UserProfile:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return UserProfile.model_validate(data)


def parse_profile_dict(data: dict) -> UserProfile:
    return UserProfile.model_validate(data)
