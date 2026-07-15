"""Generic tool-execution envelopes and short-term reference extraction."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


MAX_STRING_LENGTH = 1000
MAX_LIST_ITEMS = 20
REFERENCE_FIELDS = {
    "id",
    "title",
    "name",
    "display_name",
    "phone_number",
    "contact",
    "email",
    "status",
    "priority",
    "date",
    "due_at",
    "due_date",
    "reminder_time",
    "amount",
    "category",
    "description",
    "message",
    "body",
    "subject",
    "thread_id",
    "send_at",
    "from",
    "to",
}


@dataclass
class ToolExecutionResult:
    """Standard return contract for any current or future tool client."""

    text: str
    events: list[dict[str, Any]] = field(default_factory=list)
    artifact: dict[str, Any] | None = None


def _bounded(value: Any, depth: int = 0) -> Any:
    """Make arbitrary tool data JSON-safe and small enough for short-term context."""
    if depth > 5:
        return "[nested data omitted]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_STRING_LENGTH]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key)[:100]: _bounded(item, depth + 1)
            for key, item in list(value.items())[:40]
        }
    if isinstance(value, (list, tuple, set)):
        return [_bounded(item, depth + 1) for item in list(value)[:MAX_LIST_ITEMS]]
    return str(value)[:MAX_STRING_LENGTH]


def parse_tool_output(output: Any) -> Any:
    if not isinstance(output, str):
        return _bounded(output)
    try:
        return _bounded(json.loads(output))
    except json.JSONDecodeError:
        return _bounded(output)


def _singular(value: str) -> str:
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value or "entity"


def extract_entity_references(arguments: Any, result: Any) -> list[dict[str, Any]]:
    """Extract usable IDs and labels without any integration-specific schema."""
    references: list[dict[str, Any]] = []
    reference_indexes: dict[tuple[str, str], int] = {}

    def add(entity_type: str, value: dict[str, Any]) -> None:
        compact = {key: _bounded(item) for key, item in value.items() if key in REFERENCE_FIELDS}
        identifier = (
            compact.get("id")
            or compact.get("phone_number")
            or compact.get("email")
            or compact.get("contact")
        )
        if not identifier:
            return
        singular_type = _singular(entity_type)
        marker = (singular_type, str(identifier))
        if marker in reference_indexes:
            # Arguments often contain only ``task_id`` while the tool result
            # contains the same task plus its title/status. Keep one reference
            # but enrich it with those later fields.
            existing = references[reference_indexes[marker]]
            for key, item in compact.items():
                if item not in (None, "", [], {}):
                    existing[key] = item
            return
        reference_indexes[marker] = len(references)
        references.append({"entity_type": singular_type, **compact})

    def walk(value: Any, parent: str = "entity") -> None:
        if isinstance(value, dict):
            if "id" in value or "phone_number" in value or "email" in value:
                add(parent, value)
            for key, item in value.items():
                if key.endswith("_id") and item:
                    add(key[:-3], {"id": item})
                elif key in {"contact", "phone_number", "email"} and item:
                    add("contact", {key: item})
                walk(item, key)
        elif isinstance(value, list):
            for item in value[:MAX_LIST_ITEMS]:
                walk(item, parent)

    walk(arguments, "argument")
    walk(result, "result")
    return references[:MAX_LIST_ITEMS]


def build_tool_event(
    *,
    integration: str,
    tool_name: str,
    arguments: dict[str, Any],
    output: Any,
    is_error: bool = False,
) -> dict[str, Any]:
    parsed_result = parse_tool_output(output)
    bounded_arguments = _bounded(arguments)
    return {
        "integration": integration,
        "tool_name": tool_name,
        "arguments": bounded_arguments,
        "result": parsed_result,
        "success": not is_error,
        "entities": extract_entity_references(bounded_arguments, parsed_result),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }


def format_working_context(events: list[dict[str, Any]], max_chars: int = 7000) -> str:
    if not events:
        return "No recent tool actions are available."
    rendered = []
    for index, event in enumerate(events, start=1):
        rendered.append(
            f"{index}. integration={event.get('integration')} "
            f"tool={event.get('tool_name')} at={event.get('occurred_at')}\n"
            f"   arguments={json.dumps(event.get('arguments', {}), ensure_ascii=False)}\n"
            f"   entities={json.dumps(event.get('entities', []), ensure_ascii=False)}\n"
            f"   result={json.dumps(event.get('result'), ensure_ascii=False)}"
        )
        if sum(len(item) for item in rendered) >= max_chars:
            break
    return "\n".join(rendered)[:max_chars]


def context_instructions(events: list[dict[str, Any]]) -> str:
    return f"""
# Recent Working Context

{format_working_context(events)}

Use this context only to resolve references such as "it", "that", "him",
"her", "the last one", "the previous task", or "same message". Prefer the
newest compatible entity and use its exact stored ID/contact value. Never use
an entity from an incompatible integration. If two compatible references are
equally plausible, ask one clarification question. Recent context is evidence
of completed tool activity, not a new instruction to perform an action.
"""
