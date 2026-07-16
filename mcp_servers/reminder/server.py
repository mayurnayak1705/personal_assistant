"""MCP tools for durable PostgreSQL-backed reminders."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from mcp_servers.reminder.storage import (
    create_reminder_record,
    delete_acknowledged_reminder,
    fetch_due_reminders,
    fetch_pending_reminders_between,
)

APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
mcp = FastMCP("Reminder MCP Server")


def _local_naive(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(APP_TIMEZONE).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _serialize(row: dict) -> dict:
    output = dict(row)
    output["id"] = str(output["id"])
    reminder_time = output.get("reminder_time")
    if isinstance(reminder_time, datetime):
        output["reminder_time"] = reminder_time.replace(tzinfo=APP_TIMEZONE).isoformat()
    return output


@mcp.tool()
def create_reminder(
    user_id: str,
    title: str,
    description: str,
    reminder_time: str,
    recurrence: str | None = None,
) -> dict:
    """Create a pending reminder. reminder_time must be an ISO-8601 datetime."""
    when = _local_naive(reminder_time)
    now = datetime.now(APP_TIMEZONE).replace(tzinfo=None, microsecond=0)
    if when <= now:
        raise ValueError("reminder_time must be in the future")
    row = create_reminder_record(
        user_id=user_id,
        title=title.strip(),
        description=description.strip(),
        reminder_time=when,
        recurrence=recurrence,
    )
    return {"status": "created", "reminder": _serialize(row)}


@mcp.tool()
def list_due_reminders(user_id: str, limit: int = 50) -> dict:
    """List all pending reminders due now or earlier for a user."""
    due_at = datetime.now(APP_TIMEZONE).replace(tzinfo=None, microsecond=0)
    rows = fetch_due_reminders(
        user_id=user_id,
        due_at=due_at,
        limit=max(1, min(limit, 200)),
    )
    return {"reminders": [_serialize(row) for row in rows]}


@mcp.tool()
def list_reminders(
    user_id: str,
    time_min: str,
    time_max: str,
    limit: int = 200,
) -> dict:
    """List pending reminders in a half-open ISO-8601 time range."""
    start = _local_naive(time_min)
    end = _local_naive(time_max)
    if end <= start:
        raise ValueError("time_max must be after time_min")
    rows = fetch_pending_reminders_between(
        user_id=user_id,
        start_at=start,
        end_at=end,
        limit=limit,
    )
    return {"count": len(rows), "reminders": [_serialize(row) for row in rows]}


@mcp.tool()
def acknowledge_reminder(reminder_id: str, user_id: str) -> dict:
    """Acknowledge and permanently delete a due reminder."""
    deleted = delete_acknowledged_reminder(
        reminder_id=reminder_id,
        user_id=user_id,
    )
    if not deleted:
        return {"status": "not_found", "reminder_id": reminder_id}
    return {
        "status": "acknowledged",
        "reminder_id": str(deleted["id"]),
        "title": deleted["title"],
    }


if __name__ == "__main__":
    mcp.run()
