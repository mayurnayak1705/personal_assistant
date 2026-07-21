"""Turn generic tool events into durable, human-readable action records."""

from __future__ import annotations

from typing import Any


ACTION_VERBS = {
    "create": "Created",
    "update": "Updated",
    "complete": "Completed",
    "delete": "Deleted",
    "cancel": "Cancelled",
    "execute": "Executed",
    "retrieve": "Retrieved",
    "undo": "Undid",
    "external_event": "Received",
}


def classify_action(tool_name: str) -> str:
    """Classify current and future tools by conventional verb naming."""
    name = (tool_name or "").strip().casefold()
    if name.startswith(("acknowledge", "complete", "finish", "resolve")):
        return "complete"
    if name.startswith(("delete", "remove")):
        return "delete"
    if name.startswith("cancel"):
        return "cancel"
    if name.startswith(("create", "add", "schedule", "set")):
        return "create"
    if name.startswith(("update", "edit", "reschedule", "postpone", "reopen")):
        return "update"
    if name.startswith(("receive", "import")):
        return "external_event"
    if name.startswith(("list", "search", "find", "get", "read", "fetch", "report", "summarize", "poll")):
        return "retrieve"
    if name.startswith("undo"):
        return "undo"
    if name.startswith(("send", "play", "run", "execute", "publish")):
        return "execute"
    return "execute"


def primary_entity(event: dict[str, Any]) -> dict[str, Any] | None:
    entities = event.get("entities") or []
    if not entities:
        return None

    label_fields = ("title", "name", "display_name", "description", "email", "phone_number", "contact", "category")

    def score(entity: dict[str, Any]) -> tuple[int, int]:
        useful = sum(entity.get(field) not in (None, "") for field in label_fields)
        details = sum(value not in (None, "", [], {}) for key, value in entity.items() if key != "entity_type")
        return useful, details

    return max(entities, key=score)


def entity_identifier(entity: dict[str, Any] | None) -> str | None:
    if not entity:
        return None
    for field in ("id", "phone_number", "email", "contact"):
        if entity.get(field) not in (None, ""):
            return str(entity[field])
    return None


def entity_label(entity: dict[str, Any] | None) -> str | None:
    if not entity:
        return None
    for field in ("title", "name", "display_name", "description", "email", "phone_number", "contact", "category", "id"):
        if entity.get(field) not in (None, ""):
            return str(entity[field])
    return None


def build_action_record(event: dict[str, Any]) -> dict[str, Any]:
    action_type = classify_action(str(event.get("tool_name", "")))
    entity = primary_entity(event)
    integration = str(event.get("integration") or "unknown")
    tool_name = str(event.get("tool_name") or "unknown")
    label = entity_label(entity)
    entity_type = str((entity or {}).get("entity_type") or integration.rstrip("s") or "action")

    if integration == "whatsapp" and tool_name == "send_message":
        summary = f"Sent WhatsApp message to {label or 'contact'}"
    elif integration == "whatsapp" and tool_name == "receive_message":
        summary = f"Received WhatsApp message from {label or 'contact'}"
    else:
        subject = entity_type.replace("_", " ")
        suffix = f": {label}" if label else ""
        summary = f"{ACTION_VERBS[action_type]} {subject}{suffix}"

    return {
        "integration": integration,
        "tool_name": tool_name,
        "action_type": action_type,
        "entity_type": entity_type,
        "entity_id": entity_identifier(entity),
        "summary": summary[:500],
        "occurred_at": event.get("occurred_at"),
    }
