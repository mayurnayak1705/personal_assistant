"""Reliable PostgreSQL configuration for the local app and MCP subprocesses."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_VALUES = dotenv_values(PROJECT_ROOT / ".env")


def _value(name: str, default: str) -> str:
    """Prefer non-empty process values, then the local checkout's .env value."""

    process_value = os.getenv(name, "").strip()
    if process_value:
        return process_value
    file_value = str(ENV_VALUES.get(name) or "").strip()
    return file_value or default


def postgres_config() -> dict[str, str | int]:
    try:
        port = int(_value("POSTGRES_PORT", "5432"))
    except ValueError as exc:
        raise ValueError("POSTGRES_PORT must be a valid port number.") from exc
    return {
        "host": _value("POSTGRES_HOST", "localhost"),
        "dbname": _value("POSTGRES_DB", "ai_assistant_memory"),
        "user": _value("POSTGRES_USER", "postgres"),
        "password": _value("POSTGRES_PASSWORD", ""),
        "port": port,
    }
