"""TTL-backed PostgreSQL store for generic recent tool actions."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg.types.json import Jsonb

from app.persistence.postgres_insert import get_connection


DEFAULT_TTL_MINUTES = max(15, int(os.getenv("WORKING_CONTEXT_TTL_MINUTES", "360")))


def init_working_context_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS working_context_events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    sequence BIGSERIAL UNIQUE,
                    conversation_id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    integration VARCHAR NOT NULL,
                    tool_name VARCHAR NOT NULL,
                    event_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMPTZ NOT NULL
                );
                ALTER TABLE working_context_events
                    ADD COLUMN IF NOT EXISTS sequence BIGSERIAL;
                CREATE INDEX IF NOT EXISTS idx_working_context_conversation
                    ON working_context_events(conversation_id, user_id, sequence DESC);
                CREATE INDEX IF NOT EXISTS idx_working_context_expiry
                    ON working_context_events(expires_at);
                """
            )
            conn.commit()


def save_working_context_events(
    *,
    conversation_id: str,
    user_id: str,
    events: list[dict[str, Any]],
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
) -> int:
    successful = [event for event in events if event.get("success")]
    if not successful:
        return 0
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(15, ttl_minutes))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM working_context_events WHERE expires_at <= CURRENT_TIMESTAMP")
            for event in successful:
                cur.execute(
                    """
                    INSERT INTO working_context_events
                        (conversation_id, user_id, integration, tool_name, event_data, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        conversation_id,
                        user_id,
                        event.get("integration", "unknown"),
                        event.get("tool_name", "unknown"),
                        Jsonb(event),
                        expires_at,
                    ),
                )
            # Keep bounded even during a long-running chat.
            cur.execute(
                """
                DELETE FROM working_context_events
                WHERE conversation_id = %s AND user_id = %s AND id NOT IN (
                    SELECT id FROM working_context_events
                    WHERE conversation_id = %s AND user_id = %s
                    ORDER BY sequence DESC
                    LIMIT 30
                );
                """,
                (conversation_id, user_id, conversation_id, user_id),
            )
            conn.commit()
    return len(successful)


def fetch_working_context(
    *,
    conversation_id: str,
    user_id: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_data
                FROM working_context_events
                WHERE conversation_id = %s
                  AND user_id = %s
                  AND expires_at > CURRENT_TIMESTAMP
                ORDER BY sequence DESC
                LIMIT %s;
                """,
                (conversation_id, user_id, max(1, min(limit, 30))),
            )
            return [dict(row["event_data"]) for row in cur.fetchall()]
