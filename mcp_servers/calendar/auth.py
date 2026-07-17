"""OAuth and Google Calendar API service creation."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from google_oauth import GoogleAuthenticationRequired, load_credentials


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
DEFAULT_TOKEN_PATH = Path(__file__).with_name("token.json")
_LOCK = threading.Lock()


class CalendarAuthenticationRequired(RuntimeError):
    pass


def token_path() -> Path:
    return Path(os.getenv("CALENDAR_TOKEN_FILE", str(DEFAULT_TOKEN_PATH))).expanduser()


def _save_credentials(credentials: Credentials, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(credentials.to_json(), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(destination)


def authorize(client_secret_file: str, destination: str | None = None) -> Path:
    secret = Path(client_secret_file).expanduser().resolve()
    if not secret.is_file():
        raise FileNotFoundError(f"Google Calendar OAuth client file not found: {secret}")
    output = Path(destination).expanduser().resolve() if destination else token_path()
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        access_type="offline",
        prompt="consent",
        open_browser=True,
    )
    _save_credentials(credentials, output)
    return output


def credentials() -> Credentials:
    try:
        return load_credentials(os.getenv("DEEP_THOUGHT_USER_ID", "mayur"))
    except GoogleAuthenticationRequired:
        pass
    path = token_path()
    if not path.is_file():
        raise CalendarAuthenticationRequired(
            "Google Calendar is not connected. Run the Calendar OAuth setup command first."
        )
    with _LOCK:
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_credentials(creds, path)
        if not creds.valid:
            raise CalendarAuthenticationRequired(
                "Google Calendar authorization is invalid or expired."
            )
        return creds


def calendar_service():
    return build("calendar", "v3", credentials=credentials(), cache_discovery=False)


def connection_status() -> dict:
    path = token_path()
    if not path.is_file():
        return {"authenticated": False, "calendar_id": None, "error": "OAuth setup required"}
    try:
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        calendar_service().events().list(calendarId=calendar_id, maxResults=1).execute()
        return {"authenticated": True, "calendar_id": calendar_id, "error": None}
    except Exception as exc:
        return {"authenticated": False, "calendar_id": None, "error": str(exc)}
