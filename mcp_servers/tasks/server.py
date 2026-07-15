"""MCP tools for persistent task management."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from mcp_servers.tasks.storage import (
    create_task_record,
    delete_task_record,
    init_task_schema,
    list_task_records,
    undo_latest_task_action,
    update_task_record,
)

APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_STATUSES = {"todo", "in_progress", "completed", "cancelled"}

init_task_schema()
mcp = FastMCP("Tasks MCP Server")


def _local_naive(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(APP_TIMEZONE).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _serialize_value(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=APP_TIMEZONE).isoformat()
    return str(value) if value is not None and value.__class__.__name__ == "UUID" else value


def _serialize(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {key: _serialize_value(value) for key, value in row.items()}


@mcp.tool()
def create_task(
    user_id: str,
    title: str,
    description: str = "",
    due_at: str | None = None,
    priority: str = "normal",
    category: str | None = None,
    recurrence: str | None = None,
    source: str = "chat",
) -> dict:
    """Create an open task. A task may be created without a due date."""
    normalized_priority = priority.lower().strip()
    if normalized_priority not in VALID_PRIORITIES:
        raise ValueError("priority must be low, normal, high, or urgent")
    if not title.strip():
        raise ValueError("title is required")
    task = create_task_record(
        user_id=user_id,
        title=title.strip(),
        description=description.strip(),
        priority=normalized_priority,
        due_date=_local_naive(due_at),
        category=category.strip() if category else None,
        recurrence=recurrence.strip() if recurrence else None,
        source=source.strip() or "chat",
    )
    return {"status": "created", "task": _serialize(task)}


@mcp.tool()
def list_tasks(
    user_id: str,
    view: str = "open",
    query: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> dict:
    """List or search tasks. Views: open, due, overdue, today, upcoming, completed, cancelled, all."""
    rows = list_task_records(
        user_id=user_id,
        view=view.lower().strip(),
        now=datetime.now(APP_TIMEZONE).replace(tzinfo=None, microsecond=0),
        query=query,
        priority=priority,
        category=category,
        limit=limit,
    )
    return {"view": view, "count": len(rows), "tasks": [_serialize(row) for row in rows]}


@mcp.tool()
def update_task(
    task_id: str,
    user_id: str,
    title: str | None = None,
    description: str | None = None,
    due_at: str | None = None,
    clear_due_date: bool = False,
    priority: str | None = None,
    status: str | None = None,
    category: str | None = None,
    recurrence: str | None = None,
) -> dict:
    """Update one uniquely identified task. Use clear_due_date to remove its due date."""
    changes = {}
    for key, value in {
        "title": title,
        "description": description,
        "category": category,
        "recurrence": recurrence,
    }.items():
        if value is not None:
            changes[key] = value.strip()
    if priority is not None:
        normalized = priority.lower().strip()
        if normalized not in VALID_PRIORITIES:
            raise ValueError("priority must be low, normal, high, or urgent")
        changes["priority"] = normalized
    if status is not None:
        normalized_status = status.lower().strip()
        if normalized_status not in VALID_STATUSES:
            raise ValueError("status must be todo, in_progress, completed, or cancelled")
        changes["status"] = normalized_status
        changes["completed_at"] = (
            datetime.now(APP_TIMEZONE).replace(tzinfo=None, microsecond=0)
            if normalized_status == "completed"
            else None
        )
    if clear_due_date:
        changes["due_date"] = None
    elif due_at is not None:
        changes["due_date"] = _local_naive(due_at)

    task = update_task_record(task_id=task_id, user_id=user_id, changes=changes)
    return {"status": "updated", "task": _serialize(task)} if task else {"status": "not_found"}


@mcp.tool()
def complete_task(task_id: str, user_id: str) -> dict:
    """Mark one task completed while keeping it in task history."""
    task = update_task_record(
        task_id=task_id,
        user_id=user_id,
        changes={
            "status": "completed",
            "completed_at": datetime.now(APP_TIMEZONE).replace(tzinfo=None, microsecond=0),
        },
        action="complete",
    )
    return {"status": "completed", "task": _serialize(task)} if task else {"status": "not_found"}


@mcp.tool()
def reopen_task(task_id: str, user_id: str) -> dict:
    """Reopen a completed or cancelled task."""
    task = update_task_record(
        task_id=task_id,
        user_id=user_id,
        changes={"status": "todo", "completed_at": None},
        action="reopen",
    )
    return {"status": "reopened", "task": _serialize(task)} if task else {"status": "not_found"}


@mcp.tool()
def delete_task(task_id: str, user_id: str) -> dict:
    """Delete one uniquely identified task. Do not use for an unconfirmed bulk deletion."""
    task = delete_task_record(task_id=task_id, user_id=user_id)
    return {"status": "deleted", "task": _serialize(task)} if task else {"status": "not_found"}


@mcp.tool()
def undo_latest_task_change(user_id: str) -> dict:
    """Undo the user's latest task create, update, complete, reopen, or delete action."""
    result = undo_latest_task_action(user_id=user_id)
    if result is None:
        return {"status": "nothing_to_undo"}
    return {
        "status": "undone",
        "action": result["action"],
        "task_id": result["task_id"],
        "task": _serialize(result["task"]),
    }


if __name__ == "__main__":
    mcp.run()
