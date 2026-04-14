"""Google OAuth2 for Calendar API — token storage in PostgreSQL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from psycopg import Connection

from weekchef.config import Settings
from weekchef.db.app import oauth_token_get, oauth_token_save

# Free/busy reads + event creation (Telegram /confirm_calendar); re-auth if token lacks scopes
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def credentials_from_token_dict(
    data: dict[str, Any],
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> Credentials:
    """Build Credentials from stored token JSON (and optional web client secrets)."""
    token = data.get("token")
    refresh = data.get("refresh_token")
    tid = data.get("client_id") or client_id
    secret = data.get("client_secret") or client_secret
    return Credentials(
        token=token,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=tid,
        client_secret=secret,
        scopes=data.get("scopes") or SCOPES,
    )


def credentials_from_db(
    conn: Connection,
    user_key: str,
    settings: Settings,
) -> Credentials | None:
    raw = oauth_token_get(conn, user_key)
    if not raw:
        return None
    cid = settings.google_oauth_client_id or None
    csec = settings.google_oauth_client_secret or None
    return credentials_from_token_dict(raw, client_id=cid, client_secret=csec)


def refresh_and_persist_if_needed(
    conn: Connection,
    user_key: str,
    creds: Credentials,
) -> Credentials:
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        oauth_token_save(conn, user_key, _creds_to_storable(creds))
    return creds


def _creds_to_storable(creds: Credentials) -> dict[str, Any]:
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "scopes": list(creds.scopes or SCOPES),
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
    }


def run_installed_app_flow_and_save(
    conn: Connection,
    user_key: str,
    client_secrets_path: Path,
    *,
    redirect_port: int = 0,
) -> Credentials:
    """Interactive OAuth (browser). Saves refreshed token JSON to DB."""
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
    creds = flow.run_local_server(port=redirect_port)
    oauth_token_save(conn, user_key, _creds_to_storable(creds))
    return creds
