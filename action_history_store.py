"""Durable PostgreSQL storage for completed assistant tool actions."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from Server.postgre_insert import get_connection
from action_history import build_action_record
from follow_up_suggestions import suggestion_for_event


def init_action_history_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_action_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    sequence BIGSERIAL UNIQUE,
                    conversation_id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    integration VARCHAR NOT NULL,
                    tool_name VARCHAR NOT NULL,
                    action_type VARCHAR NOT NULL,
                    entity_type VARCHAR NOT NULL,
                    entity_id VARCHAR,
                    summary VARCHAR(500) NOT NULL,
                    event_data JSONB NOT NULL,
                    suggestion_data JSONB,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_action_history_user
                    ON assistant_action_history(user_id, sequence DESC);
                CREATE INDEX IF NOT EXISTS idx_action_history_conversation
                    ON assistant_action_history(conversation_id, user_id, sequence DESC);
                CREATE INDEX IF NOT EXISTS idx_action_history_entity
                    ON assistant_action_history(user_id, entity_type, entity_id)
                    WHERE entity_id IS NOT NULL;
                """
            )
            conn.commit()


def save_action_history_events(
    *,
    conversation_id: str,
    user_id: str,
    events: list[dict[str, Any]],
) -> int:
    successful = [event for event in events if event.get("success")]
    if not successful:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for event in successful:
                record = build_action_record(event)
                suggestion = suggestion_for_event(event)
                cur.execute(
                    """
                    INSERT INTO assistant_action_history (
                        conversation_id, user_id, integration, tool_name,
                        action_type, entity_type, entity_id, summary,
                        event_data, suggestion_data, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                              COALESCE(%s::timestamptz, CURRENT_TIMESTAMP));
                    """,
                    (
                        conversation_id,
                        user_id,
                        record["integration"],
                        record["tool_name"],
                        record["action_type"],
                        record["entity_type"],
                        record["entity_id"],
                        record["summary"],
                        Jsonb(event),
                        Jsonb(suggestion) if suggestion else None,
                        record["occurred_at"],
                    ),
                )
            conn.commit()
    return len(successful)


def fetch_action_history(
    *,
    user_id: str,
    conversation_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conditions = ["user_id = %s"]
    values: list[Any] = [user_id]
    if conversation_id:
        conditions.append("conversation_id = %s")
        values.append(conversation_id)
    values.append(max(1, min(limit, 200)))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, conversation_id, integration, tool_name, action_type,
                       entity_type, entity_id, summary, suggestion_data, created_at
                FROM assistant_action_history
                WHERE {' AND '.join(conditions)}
                ORDER BY sequence DESC
                LIMIT %s;
                """,
                values,
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(row["id"]),
            "conversation_id": row["conversation_id"],
            "integration": row["integration"],
            "tool_name": row["tool_name"],
            "action_type": row["action_type"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "summary": row["summary"],
            "created_at": row["created_at"].isoformat(),
            "suggestion": row["suggestion_data"],
        }
        for row in rows
    ]
