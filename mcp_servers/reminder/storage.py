"""PostgreSQL operations used only by the Reminder MCP server."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.persistence.postgres_insert import get_connection


def create_reminder_record(
    *,
    user_id: str,
    title: str,
    description: str,
    reminder_time: datetime,
    recurrence: str | None = None,
) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reminders
                    (user_id, title, description, reminder_time, recurrence, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                RETURNING id, user_id, title, description, reminder_time, status;
                """,
                (user_id, title, description, reminder_time, recurrence),
            )
            row = cur.fetchone()
            conn.commit()
    return dict(row)


def fetch_due_reminders(
    *,
    user_id: str,
    due_at: datetime,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, description, reminder_time, status
                FROM reminders
                WHERE user_id = %s
                  AND status = 'pending'
                  AND reminder_time <= %s
                ORDER BY reminder_time ASC, created_at ASC
                LIMIT %s;
                """,
                (user_id, due_at, limit),
            )
            return [dict(row) for row in cur.fetchall()]


def fetch_pending_reminders_between(
    *,
    user_id: str,
    start_at: datetime,
    end_at: datetime,
    limit: int = 200,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, description, reminder_time, status
                FROM reminders
                WHERE user_id = %s
                  AND status = 'pending'
                  AND reminder_time >= %s
                  AND reminder_time < %s
                ORDER BY reminder_time ASC, created_at ASC
                LIMIT %s;
                """,
                (user_id, start_at, end_at, max(1, min(limit, 200))),
            )
            return [dict(row) for row in cur.fetchall()]


def delete_acknowledged_reminder(*, reminder_id: str, user_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM reminders
                WHERE id = %s AND user_id = %s AND status = 'pending'
                RETURNING id, title;
                """,
                (reminder_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return dict(row) if row else None
