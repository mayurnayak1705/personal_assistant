"""Cross-tool daily briefing generation with partial-failure isolation."""

from __future__ import annotations

import asyncio
import os
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.features.briefing.store import (
    get_daily_briefing,
    get_previous_briefing,
    replace_daily_briefing,
    save_daily_briefing_if_new,
)
from mcp_servers.reminder.client import reminder_client
from mcp_servers.tasks.client import tasks_client
from mcp_servers.whatsappmeow.client import whatsapp_client


APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WHATSAPP_LOG = PROJECT_ROOT / "mcp_servers/whatsappmeow/whatsmeow-message-log.db"
EXPENSE_DB = PROJECT_ROOT / "mcp_servers/expense/server/expenses.db"


def _parse_local(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=APP_TIMEZONE)
    return parsed.astimezone(APP_TIMEZONE)


def _format_inr(value: float) -> str:
    rounded = int(round(value))
    sign = "-" if rounded < 0 else ""
    digits = str(abs(rounded))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    tail = digits[-3:]
    head = digits[:-3]
    groups = []
    while head:
        groups.append(head[-2:])
        head = head[:-2]
    return f"{sign}₹{','.join(reversed(groups))},{tail}"


def _expense_budget_state(now: datetime) -> dict[str, Any] | None:
    if not EXPENSE_DB.is_file():
        return None
    today = now.date().isoformat()
    with sqlite3.connect(f"file:{EXPENSE_DB}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        budgets = conn.execute(
            """
            SELECT id, start_date, end_date, amount, category
            FROM expense_budgets
            WHERE start_date <= ? AND end_date >= ?
            ORDER BY timestamp DESC, id DESC;
            """,
            (today, today),
        ).fetchall()
        states = []
        for budget in budgets:
            if budget["category"]:
                spent = conn.execute(
                    """SELECT COALESCE(SUM(amount), 0) FROM expenses
                       WHERE date BETWEEN ? AND ? AND LOWER(category) = LOWER(?)""",
                    (budget["start_date"], budget["end_date"], budget["category"]),
                ).fetchone()[0]
            else:
                spent = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date BETWEEN ? AND ?",
                    (budget["start_date"], budget["end_date"]),
                ).fetchone()[0]
            amount = float(budget["amount"])
            spent = float(spent)
            states.append({
                "category": budget["category"],
                "budget": round(amount, 2),
                "spent": round(spent, 2),
                "remaining": round(amount - spent, 2),
                "utilisation_percent": round((spent / amount) * 100, 1) if amount else None,
            })
    if not states:
        return None
    return max(states, key=lambda item: item.get("utilisation_percent") or 0)


def _whatsapp_start_cursor(since: datetime) -> int:
    if not WHATSAPP_LOG.is_file():
        return 0
    with sqlite3.connect(f"file:{WHATSAPP_LOG}?mode=ro", uri=True) as conn:
        latest = int(conn.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0])
        row = conn.execute(
            "SELECT MIN(id) FROM messages WHERE from_me = 0 AND timestamp >= ?",
            (int(since.timestamp()),),
        ).fetchone()
        return int(row[0]) - 1 if row and row[0] is not None else latest


async def _whatsapp_summary(previous: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    if not whatsapp_client.enabled:
        return {"available": False, "count": 0, "senders": [], "cursor": None}
    previous_data = (previous or {}).get("data") or {}
    cursor = ((previous_data.get("whatsapp") or {}).get("cursor"))
    if cursor is None:
        since = (previous or {}).get("created_at") or (now - timedelta(hours=24))
        cursor = await asyncio.to_thread(_whatsapp_start_cursor, since)
    payload = await whatsapp_client.poll_messages(after_id=int(cursor), limit=200)
    personal = [
        message for message in payload.get("messages", [])
        if "@newsletter" not in str(message.get("chat_jid", ""))
    ]
    counts = Counter(
        str(message.get("contact_name") or message.get("phone_number") or "Unknown contact")
        for message in personal
    )
    senders = [
        {"name": name, "count": count}
        for name, count in counts.most_common(5)
    ]
    return {
        "available": True,
        "count": len(personal),
        "senders": senders,
        "cursor": payload.get("cursor", cursor),
    }


def _briefing_text(data: dict[str, Any], now: datetime) -> str:
    parts = []
    task_data = data["tasks"]
    if task_data["due_today_count"]:
        count = task_data["due_today_count"]
        parts.append(f"{count} task{'s' if count != 1 else ''} due today")
    if task_data["overdue_count"]:
        count = task_data["overdue_count"]
        parts.append(f"{count} overdue task{'s' if count != 1 else ''}")
    reminder_data = data["reminders"]
    if reminder_data["due_count"]:
        count = reminder_data["due_count"]
        parts.append(f"{count} due reminder{'s' if count != 1 else ''}")
    if reminder_data["later_today_count"]:
        count = reminder_data["later_today_count"]
        parts.append(f"{count} reminder{'s' if count != 1 else ''} later today")
    whatsapp = data["whatsapp"]
    if whatsapp["count"]:
        sender_names = [item["name"] for item in whatsapp["senders"][:3]]
        sender_text = ", ".join(sender_names[:-1]) + (f" and {sender_names[-1]}" if len(sender_names) > 1 else sender_names[0])
        parts.append(f"{whatsapp['count']} WhatsApp message{'s' if whatsapp['count'] != 1 else ''} from {sender_text}")
    budget = data.get("budget")
    if budget:
        label = f"{budget['category']} budget" if budget.get("category") else "budget"
        remaining = budget["remaining"]
        parts.append(
            f"{_format_inr(abs(remaining))} {'left in' if remaining >= 0 else 'over'} your {label}"
        )
    if not parts:
        return "You have no due tasks, reminders, or pending WhatsApp items today."
    if len(parts) == 1:
        summary = parts[0]
    else:
        summary = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    return f"You have {summary}."


async def generate_daily_briefing(*, user_id: str, force: bool = False) -> dict[str, Any]:
    now = datetime.now(APP_TIMEZONE)
    today = now.date()
    existing = await asyncio.to_thread(get_daily_briefing, user_id=user_id, briefing_date=today)
    if existing and not force:
        return {"should_show": False, "briefing_date": today.isoformat(), **existing["data"]}

    previous = await asyncio.to_thread(get_previous_briefing, user_id=user_id, before_date=today)
    day_start = datetime.combine(today, datetime.min.time(), tzinfo=APP_TIMEZONE)
    day_end = day_start + timedelta(days=1)
    results = await asyncio.gather(
        tasks_client.list_tasks(user_id=user_id, view="all", limit=200),
        reminder_client.due_reminders(user_id=user_id, limit=200),
        reminder_client.reminders_between(
            user_id=user_id,
            time_min=day_start.isoformat(),
            time_max=day_end.isoformat(),
            limit=200,
        ),
        _whatsapp_summary(previous, now),
        asyncio.to_thread(_expense_budget_state, now),
        return_exceptions=True,
    )

    tasks_result, due_result, today_result, whatsapp_result, budget_result = results
    availability = {}
    open_tasks = [] if isinstance(tasks_result, Exception) else tasks_result.get("tasks", [])
    availability["tasks"] = not isinstance(tasks_result, Exception)
    due_today = []
    overdue = []
    for task in open_tasks:
        if task.get("status") not in {"todo", "in_progress"}:
            continue
        due = _parse_local(task.get("due_date"))
        if not due:
            continue
        if due.date() == today:
            due_today.append(task)
        elif due < day_start:
            overdue.append(task)

    due_reminders = [] if isinstance(due_result, Exception) else due_result.get("reminders", [])
    today_reminders = [] if isinstance(today_result, Exception) else today_result.get("reminders", [])
    availability["reminders"] = not isinstance(due_result, Exception) and not isinstance(today_result, Exception)
    due_ids = {item.get("id") for item in due_reminders}
    later_today = [item for item in today_reminders if item.get("id") not in due_ids and (_parse_local(item.get("reminder_time")) or now) > now]
    whatsapp = whatsapp_result if isinstance(whatsapp_result, dict) else {"available": False, "count": 0, "senders": [], "cursor": None}
    availability["whatsapp"] = whatsapp.get("available", False)
    budget = None if isinstance(budget_result, Exception) else budget_result
    availability["expenses"] = not isinstance(budget_result, Exception)

    data = {
        "text": "",
        "tasks": {
            "due_today_count": len(due_today),
            "overdue_count": len(overdue),
            "due_today": [{"id": task.get("id"), "title": task.get("title"), "due_date": task.get("due_date")} for task in due_today[:5]],
            "overdue": [{"id": task.get("id"), "title": task.get("title"), "due_date": task.get("due_date")} for task in overdue[:5]],
        },
        "reminders": {
            "due_count": len(due_reminders),
            "later_today_count": len(later_today),
            "due": due_reminders[:5],
            "later_today": later_today[:5],
        },
        "whatsapp": whatsapp,
        "budget": budget,
        "availability": availability,
    }
    data["text"] = _briefing_text(data, now)

    if force:
        await asyncio.to_thread(replace_daily_briefing, user_id=user_id, briefing_date=today, data=data)
        inserted = True
    else:
        inserted = await asyncio.to_thread(save_daily_briefing_if_new, user_id=user_id, briefing_date=today, data=data)
        if not inserted:
            winner = await asyncio.to_thread(get_daily_briefing, user_id=user_id, briefing_date=today)
            if winner:
                data = winner["data"]
    return {"should_show": bool(force or inserted), "briefing_date": today.isoformat(), **data}
