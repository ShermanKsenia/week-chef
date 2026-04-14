"""Store Google Calendar OAuth tokens in PostgreSQL for a given user_key."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from weekchef.calendar.oauth import run_installed_app_flow_and_save
from weekchef.config import get_settings
from weekchef.db.pool import sync_connection


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--user-key",
        required=True,
        help="Stable id (e.g. profile user_id or telegram id string)",
    )
    p.add_argument(
        "--secrets",
        type=Path,
        default=None,
        help="Path to Google OAuth client JSON (default: GOOGLE_CLIENT_SECRETS_FILE)",
    )
    p.add_argument("--dsn", default=None, help="Override DATABASE_URL")
    p.add_argument("--port", type=int, default=0, help="Local redirect server port (0 = auto)")
    args = p.parse_args()

    settings = get_settings()
    secrets = args.secrets or Path(settings.google_client_secrets_file)
    if not secrets.is_file():
        print(f"Missing client secrets file: {secrets}", file=sys.stderr)
        return 1

    dsn = args.dsn or settings.database_url
    try:
        with sync_connection(dsn) as conn:
            run_installed_app_flow_and_save(
                conn,
                args.user_key,
                secrets,
                redirect_port=args.port,
            )
    except Exception as e:  # noqa: BLE001
        print(f"OAuth failed: {e}", file=sys.stderr)
        return 1

    print(f"Saved Google token for user_key={args.user_key!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
