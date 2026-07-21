"""PostgreSQL persistence for scheduled Gmail messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from app.persistence.postgres_insert import get_connection


def init_gmail_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_emails (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR NOT NULL,
                    recipients JSONB NOT NULL,
                    subject VARCHAR NOT NULL,
                    body TEXT NOT NULL,
                    send_at TIMESTAMPTZ NOT NULL,
                    status VARCHAR NOT NULL DEFAULT 'scheduled',
                    gmail_message_id VARCHAR,
                    error TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMPTZ
                );
                CREATE INDEX IF NOT EXISTS idx_scheduled_emails_due
                    ON scheduled_emails(status, send_at);
                CREATE INDEX IF NOT EXISTS idx_scheduled_emails_user
                    ON scheduled_emails(user_id, created_at DESC);
                """
            )
            conn.commit()


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        **{
            field: row[field].isoformat() if row.get(field) else None
            for field in ("send_at", "created_at", "updated_at", "sent_at")
        },
    }


def create_scheduled_email(*, user_id: str, recipients: dict, subject: str, body: str, send_at: datetime) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scheduled_emails (user_id, recipients, subject, body, send_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (user_id, Jsonb(recipients), subject, body, send_at),
            )
            row = dict(cur.fetchone())
            conn.commit()
    return _serialize(row)


def list_scheduled_emails(*, user_id: str, status: str = "scheduled", limit: int = 50) -> list[dict]:
    conditions = ["user_id = %s"]
    values: list[Any] = [user_id]
    if status != "all":
        conditions.append("status = %s")
        values.append(status)
    values.append(max(1, min(limit, 200)))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM scheduled_emails WHERE {' AND '.join(conditions)} ORDER BY send_at ASC LIMIT %s;",
                values,
            )
            return [_serialize(dict(row)) for row in cur.fetchall()]


def cancel_scheduled_email(*, schedule_id: str, user_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE scheduled_emails
                SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s AND status = 'scheduled'
                RETURNING *;
                """,
                (schedule_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return _serialize(dict(row)) if row else None


def claim_due_emails(limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH due AS (
                    SELECT id FROM scheduled_emails
                    WHERE status = 'scheduled' AND send_at <= CURRENT_TIMESTAMP
                    ORDER BY send_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE scheduled_emails AS email
                SET status = 'sending', updated_at = CURRENT_TIMESTAMP
                FROM due WHERE email.id = due.id
                RETURNING email.*;
                """,
                (max(1, min(limit, 50)),),
            )
            rows = [_serialize(dict(row)) for row in cur.fetchall()]
            conn.commit()
    return rows


def finish_scheduled_email(schedule_id: str, *, message_id: str | None = None, error: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE scheduled_emails
                SET status = %s, gmail_message_id = %s, error = %s,
                    sent_at = CASE WHEN %s IS NULL THEN CURRENT_TIMESTAMP ELSE sent_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                ("failed" if error else "sent", message_id, error, error, schedule_id),
            )
            conn.commit()
