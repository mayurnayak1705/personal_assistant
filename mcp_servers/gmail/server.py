"""MCP tools for Gmail and durable scheduled delivery."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from mcp_servers.gmail.auth import connection_status, gmail_service
from mcp_servers.gmail.messages import (
    addresses,
    create_draft as create_gmail_draft,
    get_message,
    list_messages,
    reply_to_message,
    send_message,
)
from mcp_servers.gmail.storage import (
    cancel_scheduled_email as cancel_record,
    claim_due_emails,
    create_scheduled_email,
    finish_scheduled_email,
    init_gmail_schema,
    list_scheduled_emails as list_scheduled_records,
)


APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
init_gmail_schema()
mcp = FastMCP("Gmail MCP Server")


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=APP_TIMEZONE)
    return parsed


@mcp.tool()
def gmail_status() -> dict:
    """Check whether Gmail OAuth is connected and return the authenticated address."""
    return connection_status()


@mcp.tool()
def list_emails(query: str = "in:inbox", limit: int = 10) -> dict:
    """List Gmail messages using Gmail search syntax, such as is:unread or from:name@example.com."""
    return list_messages(gmail_service(), query=query, limit=limit)


@mcp.tool()
def list_unread_emails(limit: int = 20) -> dict:
    """List unread inbox emails with sender, subject, timestamp, snippet, and stable message ID."""
    return list_messages(gmail_service(), query="in:inbox is:unread", limit=limit)


@mcp.tool()
def read_email(message_id: str) -> dict:
    """Read one Gmail message by its stable message ID, including its body."""
    return {"status": "read", "email": get_message(gmail_service(), message_id)}


@mcp.tool()
def create_draft(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
    """Create a Gmail draft without sending it."""
    return create_gmail_draft(gmail_service(), to=to, subject=subject, body=body, cc=cc, bcc=bcc)


@mcp.tool()
def send_email(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
    """Send an email immediately. Call only when the user explicitly authorizes sending."""
    return send_message(gmail_service(), to=to, subject=subject, body=body, cc=cc, bcc=bcc)


@mcp.tool()
def reply_to_email(message_id: str, body: str, cc: str = "") -> dict:
    """Reply in the existing Gmail thread. Call only when the user explicitly asks to send the reply."""
    return reply_to_message(gmail_service(), message_id=message_id, body=body, cc=cc)


@mcp.tool()
def mark_email_read(message_id: str) -> dict:
    """Mark one Gmail message as read."""
    result = gmail_service().users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()
    return {"status": "updated", "email": {"id": result.get("id"), "unread": False}}


@mcp.tool()
def archive_email(message_id: str) -> dict:
    """Archive one Gmail message by removing it from the inbox."""
    result = gmail_service().users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
    ).execute()
    return {"status": "archived", "email": {"id": result.get("id")}}


@mcp.tool()
def schedule_email(
    user_id: str,
    to: str,
    subject: str,
    body: str,
    send_at: str,
    cc: str = "",
    bcc: str = "",
) -> dict:
    """Schedule an email for durable future delivery. send_at must be an ISO-8601 datetime."""
    scheduled_at = _datetime(send_at)
    if scheduled_at <= datetime.now(APP_TIMEZONE):
        raise ValueError("send_at must be in the future; use send_email for immediate delivery")
    recipients = {"to": addresses(to), "cc": addresses(cc), "bcc": addresses(bcc)}
    if not recipients["to"]:
        raise ValueError("At least one To address is required")
    record = create_scheduled_email(
        user_id=user_id,
        recipients=recipients,
        subject=subject.strip(),
        body=body,
        send_at=scheduled_at,
    )
    return {"status": "scheduled", "scheduled_email": record}


@mcp.tool()
def list_scheduled_emails(user_id: str, status: str = "scheduled", limit: int = 50) -> dict:
    """List scheduled email records. Status may be scheduled, sent, failed, cancelled, or all."""
    allowed = {"scheduled", "sent", "failed", "cancelled", "all"}
    if status not in allowed:
        raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
    emails = list_scheduled_records(user_id=user_id, status=status, limit=limit)
    return {"status": status, "count": len(emails), "scheduled_emails": emails}


@mcp.tool()
def cancel_scheduled_email(schedule_id: str, user_id: str) -> dict:
    """Cancel one email that has not started sending."""
    record = cancel_record(schedule_id=schedule_id, user_id=user_id)
    return {"status": "cancelled", "scheduled_email": record} if record else {"status": "not_found"}


@mcp.tool()
def dispatch_due_scheduled_emails(limit: int = 10) -> dict:
    """Internal scheduler operation; deliver all currently due email records."""
    service = gmail_service()
    claimed = claim_due_emails(limit=limit)
    sent = []
    failed = []
    for record in claimed:
        try:
            recipients = record["recipients"]
            result = send_message(
                service,
                to=recipients.get("to", []),
                cc=recipients.get("cc", []),
                bcc=recipients.get("bcc", []),
                subject=record["subject"],
                body=record["body"],
            )
            message_id = result["message"]["id"]
            finish_scheduled_email(record["id"], message_id=message_id)
            sent.append({"schedule_id": record["id"], "message_id": message_id})
        except Exception as exc:
            finish_scheduled_email(record["id"], error=str(exc)[:2000])
            failed.append({"schedule_id": record["id"], "error": str(exc)})
    return {"status": "dispatched", "sent": sent, "failed": failed}


if __name__ == "__main__":
    try:
        mcp.run()
    except* BrokenPipeError:
        # The parent app may close stdio during reload/shutdown while a final
        # scheduler response is being written. This is a normal transport
        # teardown, not a Gmail operation failure.
        pass
