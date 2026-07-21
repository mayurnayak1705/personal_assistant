"""Shared Google OAuth lifecycle for the local Deep Thought application."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from app.features.profile.store import DEFAULT_USER_ID

try:  # Optional at development time; included in requirements for releases.
    import keyring
except Exception:  # pragma: no cover - exercised on systems without a keyring backend
    keyring = None


GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
)

_KEYRING_SERVICE = "deep-thought.google-oauth"
_PENDING_TTL_SECONDS = 10 * 60
_PENDING_FLOWS: dict[str, tuple[float, str, Flow]] = {}
_FLOW_LOCK = threading.Lock()
_CREDENTIAL_LOCK = threading.Lock()


class GoogleAuthenticationRequired(RuntimeError):
    pass


class GoogleConfigurationRequired(RuntimeError):
    pass


def _safe_user_id(user_id: str) -> str:
    safe_user = "".join(character for character in user_id if character.isalnum() or character in "-_")
    return safe_user or DEFAULT_USER_ID


def _storage_root() -> Path:
    configured = os.getenv("DEEP_THOUGHT_CREDENTIALS_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".deep-thought" / "credentials"


def _credential_file(user_id: str) -> Path:
    return _storage_root() / f"google-{_safe_user_id(user_id)}.json"


def _client_config_file(user_id: str) -> Path:
    return _storage_root() / f"google-oauth-{_safe_user_id(user_id)}.json"


def validate_client_config(client_config: dict[str, Any]) -> dict[str, Any]:
    """Accept only Google Desktop OAuth JSON and reject arbitrary endpoints."""
    if not isinstance(client_config, dict) or not isinstance(client_config.get("installed"), dict):
        raise ValueError("Select a Google Desktop OAuth client JSON file.")
    installed = dict(client_config["installed"])
    required = ("client_id", "auth_uri", "token_uri")
    missing = [field for field in required if not installed.get(field)]
    if missing:
        raise ValueError(f"OAuth JSON is missing: {', '.join(missing)}")
    if not str(installed["client_id"]).endswith(".apps.googleusercontent.com"):
        raise ValueError("The OAuth client ID is not a Google client ID.")
    auth_url = urlparse(str(installed["auth_uri"]))
    token_url = urlparse(str(installed["token_uri"]))
    if auth_url.scheme != "https" or auth_url.hostname != "accounts.google.com":
        raise ValueError("OAuth authorization must use accounts.google.com.")
    if token_url.scheme != "https" or token_url.hostname != "oauth2.googleapis.com":
        raise ValueError("OAuth tokens must use oauth2.googleapis.com.")
    installed.setdefault("client_secret", "")
    return {"installed": installed}


def save_client_config(user_id: str, client_config: dict[str, Any]) -> dict[str, Any]:
    validated = validate_client_config(client_config)
    path = _client_config_file(user_id)
    if path.is_file():
        try:
            previous = validate_client_config(json.loads(path.read_text(encoding="utf-8")))
            if previous["installed"]["client_id"] != validated["installed"]["client_id"]:
                delete_credentials(user_id)
        except Exception:
            delete_credentials(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(validated), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    installed = validated["installed"]
    return {
        "configured": True,
        "project_id": installed.get("project_id"),
        "client_id_suffix": str(installed["client_id"])[-28:],
    }


def load_client_config(user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    path = _client_config_file(user_id)
    if not path.is_file():
        raise GoogleConfigurationRequired(
            "Google OAuth is not configured. Add your Desktop OAuth JSON in Settings."
        )
    return validate_client_config(json.loads(path.read_text(encoding="utf-8")))


def _read_payload(user_id: str) -> str | None:
    if keyring is not None:
        try:
            payload = keyring.get_password(_KEYRING_SERVICE, user_id)
            if payload:
                return payload
        except Exception:
            pass
    path = _credential_file(user_id)
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _write_payload(user_id: str, payload: str) -> str:
    if keyring is not None:
        try:
            keyring.set_password(_KEYRING_SERVICE, user_id, payload)
            fallback = _credential_file(user_id)
            if fallback.exists():
                fallback.unlink()
            return "keyring"
        except Exception:
            pass
    path = _credential_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    return "protected_file"


def save_credentials(user_id: str, credentials: Credentials) -> str:
    with _CREDENTIAL_LOCK:
        return _write_payload(user_id, credentials.to_json())


def load_credentials(user_id: str = DEFAULT_USER_ID) -> Credentials:
    with _CREDENTIAL_LOCK:
        payload = _read_payload(user_id)
        if not payload:
            raise GoogleAuthenticationRequired("Google is not connected. Open Settings and connect Google.")
        credentials = Credentials.from_authorized_user_info(json.loads(payload), GOOGLE_SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            _write_payload(user_id, credentials.to_json())
        if not credentials.valid:
            raise GoogleAuthenticationRequired("Google authorization is invalid or expired.")
        return credentials


def delete_credentials(user_id: str = DEFAULT_USER_ID) -> None:
    with _CREDENTIAL_LOCK:
        if keyring is not None:
            try:
                keyring.delete_password(_KEYRING_SERVICE, user_id)
            except Exception:
                pass
        path = _credential_file(user_id)
        if path.exists():
            path.unlink()


def begin_authorization(*, user_id: str, redirect_uri: str) -> dict[str, str]:
    client_config = load_client_config(user_id)
    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
        autogenerate_code_verifier=True,
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    now = time.monotonic()
    with _FLOW_LOCK:
        expired = [key for key, (created, _user, _flow) in _PENDING_FLOWS.items() if now - created > _PENDING_TTL_SECONDS]
        for key in expired:
            _PENDING_FLOWS.pop(key, None)
        _PENDING_FLOWS[state] = (now, user_id, flow)
    return {"authorization_url": authorization_url, "state": state}


def complete_authorization(*, state: str, code: str) -> dict[str, Any]:
    with _FLOW_LOCK:
        pending = _PENDING_FLOWS.pop(state, None)
    if not pending:
        raise ValueError("This Google authorization request expired. Please start again from Settings.")
    created, user_id, flow = pending
    if time.monotonic() - created > _PENDING_TTL_SECONDS:
        raise ValueError("This Google authorization request expired. Please start again from Settings.")
    flow.fetch_token(code=code)
    storage = save_credentials(user_id, flow.credentials)
    return {"user_id": user_id, "storage": storage}


def connection_status(user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    try:
        client_config = load_client_config(user_id)
        project_id = client_config["installed"].get("project_id")
    except Exception as exc:
        return {
            "configured": False,
            "connected": False,
            "email": None,
            "gmail": False,
            "calendar": False,
            "project_id": None,
            "error": str(exc),
        }
    try:
        credentials = load_credentials(user_id)
        profile = build("gmail", "v1", credentials=credentials, cache_discovery=False).users().getProfile(userId="me").execute()
        return {
            "configured": True,
            "connected": True,
            "email": profile.get("emailAddress"),
            "gmail": True,
            "calendar": True,
            "project_id": project_id,
            "error": None,
        }
    except GoogleAuthenticationRequired:
        return {
            "configured": True,
            "connected": False,
            "email": None,
            "gmail": False,
            "calendar": False,
            "project_id": project_id,
            "error": None,
        }
    except Exception as exc:
        return {
            "configured": True,
            "connected": False,
            "email": None,
            "gmail": False,
            "calendar": False,
            "project_id": project_id,
            "error": str(exc),
        }
