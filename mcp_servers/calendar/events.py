"""Validation, Google Calendar event creation, and response serialization."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def parse_datetime(value: str, default_timezone: ZoneInfo) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("start_time must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_timezone)
    return parsed.replace(microsecond=0)


def validate_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {value}") from exc


def normalize_attendees(attendee_emails: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in attendee_emails:
        email = raw.strip().lower()
        if not EMAIL_PATTERN.fullmatch(email):
            raise ValueError(f"Invalid attendee email address: {raw}")
        if email not in seen:
            seen.add(email)
            unique.append(email)
    if not unique:
        raise ValueError("At least one attendee email is required")
    return unique


def meet_url(event: dict[str, Any]) -> str | None:
    if event.get("hangoutLink"):
        return str(event["hangoutLink"])
    for entry in (event.get("conferenceData") or {}).get("entryPoints", []):
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return str(entry["uri"])
    return None


def serialize_event(event: dict[str, Any]) -> dict[str, Any]:
    conference = event.get("conferenceData") or {}
    return {
        "id": event.get("id"),
        "title": event.get("summary"),
        "description": event.get("description", ""),
        "start": (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date"),
        "end": (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date"),
        "attendees": [item.get("email") for item in event.get("attendees", []) if item.get("email")],
        "meet_url": meet_url(event),
        "conference_status": ((conference.get("createRequest") or {}).get("status") or {}).get("statusCode"),
        "calendar_url": event.get("htmlLink"),
        "status": event.get("status"),
    }


def create_meeting(
    service: Any,
    *,
    calendar_id: str,
    title: str,
    start_time: str,
    attendee_emails: list[str],
    duration_minutes: int,
    description: str,
    timezone_name: str,
) -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValueError("title is required")
    if duration_minutes < 5 or duration_minutes > 1440:
        raise ValueError("duration_minutes must be between 5 and 1440")

    timezone = validate_timezone(timezone_name)
    start = parse_datetime(start_time, timezone).astimezone(timezone)
    end = start + timedelta(minutes=duration_minutes)
    attendees = normalize_attendees(attendee_emails)
    request_id = uuid.uuid4().hex
    body = {
        "summary": title,
        "description": description.strip(),
        "start": {"dateTime": start.isoformat(), "timeZone": timezone.key},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone.key},
        "attendees": [{"email": email} for email in attendees],
        "conferenceData": {
            "createRequest": {
                "requestId": request_id,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    event = service.events().insert(
        calendarId=calendar_id,
        body=body,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()

    # Google creates conference data asynchronously. In the common case the
    # insert response already has the link; otherwise briefly refresh the event
    # so the chat response can include the actual Meet URL.
    if event.get("id") and not meet_url(event):
        for _ in range(4):
            status = (((event.get("conferenceData") or {}).get("createRequest") or {}).get("status") or {}).get("statusCode")
            if status == "failure":
                break
            time.sleep(0.5)
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event["id"],
            ).execute()
            if meet_url(event):
                break
    return serialize_event(event)
