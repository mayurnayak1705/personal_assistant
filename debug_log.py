"""Small terminal debug logger safe for MCP stdio servers."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime
from typing import Any


ENABLED = os.getenv("DEEP_THOUGHT_DEBUG", "1").strip().lower() not in {"0", "false", "off", "no"}
SENSITIVE_KEYS = {"password", "token", "access_token", "refresh_token", "client_secret", "authorization", "body", "message", "user_input", "system_prompt"}


def _safe(value: Any, key: str = "") -> Any:
    if key.casefold() in SENSITIVE_KEYS:
        text = str(value or "")
        return f"<redacted:{len(text)} chars>"
    if isinstance(value, dict):
        return {str(k): _safe(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value[:20]] + ([f"<{len(value) - 20} more>"] if len(value) > 20 else [])
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value)
    if len(text) > 800:
        return text[:800] + f"… <{len(text) - 800} chars omitted>"
    return value


def debug(area: str, event: str, **fields: Any) -> None:
    if not ENABLED:
        return
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    payload = json.dumps(_safe(fields), ensure_ascii=False, default=str, separators=(",", ":"))
    print(f"[DEBUG][{area.upper()}] {timestamp} {event} {payload}", file=sys.stderr, flush=True)


def compact_query(query: Any) -> str:
    return re.sub(r"\s+", " ", str(query)).strip()


def _masked_sql(query: Any) -> str:
    compact = compact_query(query)
    return re.sub(
        r"'(?:''|[^'])*'",
        lambda match: f"'<text:{max(0, len(match.group(0)) - 2)} chars>'",
        compact,
    )


def _database_parameters(params: Any) -> Any:
    if isinstance(params, dict):
        return {key: _database_parameters(value) for key, value in params.items()}
    if isinstance(params, (list, tuple)):
        return [_database_parameters(value) for value in params]
    if isinstance(params, str):
        return f"<text:{len(params)} chars>"
    if isinstance(params, (bytes, bytearray, memoryview)):
        return f"<binary:{len(params)} bytes>"
    return params


def sqlite_trace(database: str):
    def emit(statement: str) -> None:
        debug("DB", "query", engine="sqlite", database=database, query=_masked_sql(statement))
    return emit


def install_sqlite_tracing() -> None:
    """Trace every SQLite connection in the current process exactly once."""
    import sqlite3

    current = sqlite3.connect
    if getattr(current, "_deep_thought_debug", False):
        return

    def traced_connect(database, *args, **kwargs):
        debug("DB", "connect", engine="sqlite", database=str(database))
        connection = current(database, *args, **kwargs)
        connection.set_trace_callback(sqlite_trace(str(database)))
        return connection

    traced_connect._deep_thought_debug = True
    sqlite3.connect = traced_connect


def postgres_connection(config: dict[str, Any], *, row_factory=None):
    """Create a psycopg connection whose cursors log every SQL execution."""
    import psycopg

    class DebugCursor(psycopg.Cursor):
        def execute(self, query, params=None, *, prepare=None, binary=None):
            debug("DB", "query", engine="postgresql", database=config.get("dbname"),
                  host=config.get("host"), query=compact_query(query),
                  parameters=_database_parameters(params))
            return super().execute(query, params, prepare=prepare, binary=binary)

    debug("DB", "connect", engine="postgresql", database=config.get("dbname"),
          host=config.get("host"), port=config.get("port"), user=config.get("user"))
    return psycopg.connect(**config, row_factory=row_factory, cursor_factory=DebugCursor)
