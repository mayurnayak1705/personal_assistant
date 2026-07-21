"""PostgreSQL persistence for once-per-day personal briefings."""

from __future__ import annotations

from datetime import date, time
from typing import Any

from psycopg.types.json import Jsonb

from app.persistence.postgres_insert import get_connection


def init_daily_briefing_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_briefings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR NOT NULL,
                    briefing_date DATE NOT NULL,
                    briefing_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, briefing_date)
                );
                CREATE INDEX IF NOT EXISTS idx_daily_briefings_user_date
                    ON daily_briefings(user_id, briefing_date DESC);

                CREATE TABLE IF NOT EXISTS daily_briefing_preferences (
                    user_id VARCHAR PRIMARY KEY,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    briefing_time TIME NOT NULL DEFAULT TIME '09:00',
                    timezone VARCHAR NOT NULL DEFAULT 'Asia/Kolkata',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()


def get_daily_briefing_preference(*, user_id: str) -> dict[str, Any]:
    """Return the user's schedule, with a safe 9 AM default."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT enabled, briefing_time, timezone, updated_at
                FROM daily_briefing_preferences
                WHERE user_id = %s;
                """,
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return {
            "enabled": True,
            "briefing_time": time(hour=9),
            "timezone": "Asia/Kolkata",
            "updated_at": None,
        }
    return dict(row)


def set_daily_briefing_preference(
    *,
    user_id: str,
    briefing_time: time,
    enabled: bool = True,
    timezone: str = "Asia/Kolkata",
) -> dict[str, Any]:
    """Create or update the user's durable daily briefing schedule."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_briefing_preferences
                    (user_id, enabled, briefing_time, timezone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    briefing_time = EXCLUDED.briefing_time,
                    timezone = EXCLUDED.timezone,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING enabled, briefing_time, timezone, updated_at;
                """,
                (user_id, enabled, briefing_time, timezone),
            )
            row = cur.fetchone()
            conn.commit()
    return dict(row)


def get_daily_briefing(*, user_id: str, briefing_date: date) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT briefing_data, created_at
                FROM daily_briefings
                WHERE user_id = %s AND briefing_date = %s;
                """,
                (user_id, briefing_date),
            )
            row = cur.fetchone()
    return {"data": dict(row["briefing_data"]), "created_at": row["created_at"]} if row else None


def get_previous_briefing(*, user_id: str, before_date: date) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT briefing_data, created_at
                FROM daily_briefings
                WHERE user_id = %s AND briefing_date < %s
                ORDER BY briefing_date DESC LIMIT 1;
                """,
                (user_id, before_date),
            )
            row = cur.fetchone()
    return {"data": dict(row["briefing_data"]), "created_at": row["created_at"]} if row else None


def save_daily_briefing_if_new(*, user_id: str, briefing_date: date, data: dict[str, Any]) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_briefings (user_id, briefing_date, briefing_data)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, briefing_date) DO NOTHING
                RETURNING id;
                """,
                (user_id, briefing_date, Jsonb(data)),
            )
            inserted = cur.fetchone() is not None
            conn.commit()
    return inserted


def replace_daily_briefing(*, user_id: str, briefing_date: date, data: dict[str, Any]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_briefings (user_id, briefing_date, briefing_data)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, briefing_date) DO UPDATE SET
                    briefing_data = EXCLUDED.briefing_data,
                    created_at = CURRENT_TIMESTAMP;
                """,
                (user_id, briefing_date, Jsonb(data)),
            )
            conn.commit()
