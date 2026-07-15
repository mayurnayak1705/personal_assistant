"""Small, extensible registry of optional post-action suggestions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from action_history import entity_label, primary_entity


Suggestion = dict[str, str]
SuggestionBuilder = Callable[[dict[str, Any]], Suggestion | None]
_RULES: list[tuple[str, frozenset[str], SuggestionBuilder]] = []


def register(integration: str, *tool_names: str):
    def decorator(builder: SuggestionBuilder) -> SuggestionBuilder:
        _RULES.append((integration, frozenset(tool_names), builder))
        return builder
    return decorator


def _suggestion(label: str, prompt: str, reason: str) -> Suggestion:
    return {"type": "prompt", "label": label, "prompt": prompt, "reason": reason}


@register("whatsapp", "send_message")
def _after_whatsapp_send(event: dict[str, Any]) -> Suggestion:
    contact = entity_label(primary_entity(event)) or "this contact"
    return _suggestion(
        "Remind me to follow up tomorrow",
        f"Remind me tomorrow to follow up with {contact}",
        "A sent message may need a follow-up.",
    )


@register("whatsapp", "receive_message")
def _after_whatsapp_receive(event: dict[str, Any]) -> Suggestion:
    contact = entity_label(primary_entity(event)) or "this contact"
    return _suggestion("Reply", f"Reply to {contact} on WhatsApp", "This message has not been replied to here.")


@register("tasks", "create_task")
def _after_task_create(event: dict[str, Any]) -> Suggestion:
    entity = primary_entity(event) or {}
    title = entity_label(entity) or "this task"
    due_at = entity.get("due_at") or entity.get("due_date")
    if due_at:
        return _suggestion(
            "Add a reminder",
            f"Remind me 30 minutes before {due_at} to {title}",
            "The task has a due date but no linked reminder was created.",
        )
    return _suggestion(
        "Add a due date",
        f'Set a due date for the task "{title}"',
        "The task was created without a due date.",
    )


@register("tasks", "complete_task")
def _after_task_complete(_event: dict[str, Any]) -> Suggestion:
    return _suggestion("Show remaining tasks", "Show my remaining tasks for today", "Review what is still open.")


@register("expenses", "add_expense", "create_expense")
def _after_expense_add(_event: dict[str, Any]) -> Suggestion:
    return _suggestion("View monthly spending", "Show my spending for this month", "See how this expense affects the month.")


@register("gmail", "send_email", "reply_to_email")
def _after_email_send(event: dict[str, Any]) -> Suggestion:
    entity = primary_entity(event) or {}
    recipients = entity.get("to") or "the recipient"
    if isinstance(recipients, list):
        recipients = ", ".join(str(item) for item in recipients)
    return _suggestion(
        "Remind me to follow up",
        f"Remind me in two days to follow up with {recipients}",
        "A sent email may need a follow-up.",
    )


@register("gmail", "create_draft")
def _after_email_draft(_event: dict[str, Any]) -> Suggestion:
    return _suggestion("Review my drafts", "Show my Gmail drafts", "Review the draft before sending it.")


@register("gmail", "schedule_email")
def _after_email_schedule(_event: dict[str, Any]) -> Suggestion:
    return _suggestion(
        "View scheduled email",
        "Show my scheduled Gmail messages",
        "Review upcoming automatic deliveries.",
    )


def suggestion_for_event(event: dict[str, Any]) -> Suggestion | None:
    if not event.get("success"):
        return None
    integration = str(event.get("integration") or "")
    tool_name = str(event.get("tool_name") or "")
    for rule_integration, tool_names, builder in _RULES:
        if integration == rule_integration and tool_name in tool_names:
            return builder(event)
    return None


def choose_follow_up(events: list[dict[str, Any]]) -> Suggestion | None:
    """Return no more than one suggestion, preferring the newest action."""
    for event in reversed(events):
        suggestion = suggestion_for_event(event)
        if suggestion:
            return suggestion
    return None
