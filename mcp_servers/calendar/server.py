"""MCP tools for Google Calendar events with unique Google Meet links."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from mcp_servers.calendar.auth import calendar_service, connection_status
from mcp_servers.calendar.events import create_meeting, parse_datetime, serialize_event


APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
mcp = FastMCP("Google Calendar MCP Server")


@mcp.tool()
def calendar_status() -> dict:
    """Check whether Google Calendar OAuth is connected."""
    return connection_status()


@mcp.tool()
def create_calendar_meeting(
    title: str,
    start_time: str,
    attendee_emails: list[str],
    duration_minutes: int = 30,
    description: str = "",
    timezone: str = "",
) -> dict:
    """Create a Calendar event, invite all attendee emails, email invitations, and generate a unique Google Meet. start_time must be ISO-8601; duration defaults to 30 minutes."""
    event = create_meeting(
        calendar_service(),
        calendar_id=CALENDAR_ID,
        title=title,
        start_time=start_time,
        attendee_emails=attendee_emails,
        duration_minutes=duration_minutes,
        description=description,
        timezone_name=timezone or APP_TIMEZONE.key,
    )
    status = "created" if event.get("meet_url") else "created_meet_pending"
    return {"status": status, "meeting": event}


@mcp.tool()
def list_calendar_events(
    time_min: str = "",
    time_max: str = "",
    limit: int = 20,
) -> dict:
    """List upcoming Calendar events. Optional bounds must be ISO-8601 datetimes."""
    start = parse_datetime(time_min, APP_TIMEZONE) if time_min else datetime.now(APP_TIMEZONE)
    end = parse_datetime(time_max, APP_TIMEZONE) if time_max else start + timedelta(days=30)
    if end <= start:
        raise ValueError("time_max must be after time_min")
    result = calendar_service().events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        maxResults=max(1, min(limit, 100)),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = [serialize_event(event) for event in result.get("items", [])]
    return {"status": "listed", "count": len(events), "events": events}


@mcp.tool()
def cancel_calendar_event(event_id: str) -> dict:
    """Cancel one Calendar event by ID and notify all attendees."""
    calendar_service().events().delete(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        sendUpdates="all",
    ).execute()
    return {"status": "cancelled", "event_id": event_id}


if __name__ == "__main__":
    mcp.run()
