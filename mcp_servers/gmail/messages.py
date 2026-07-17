"""Gmail message encoding, decoding, and API operations."""

from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from html.parser import HTMLParser
from typing import Any


def addresses(value: str | list[str] | None) -> list[str]:
    if not value:
        return []
    raw = value if isinstance(value, list) else [value]
    parsed = [address.strip() for _name, address in getaddresses(raw) if address.strip()]
    if not parsed:
        raise ValueError("At least one valid email address is required")
    return parsed


def _header(headers: list[dict[str, str]], name: str) -> str:
    wanted = name.casefold()
    return next((item.get("value", "") for item in headers if item.get("name", "").casefold() == wanted), "")


def _decode(data: str | None) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode("ascii") + b"=" * (-len(data) % 4)).decode("utf-8", errors="replace")


class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag.casefold() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_to_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(value)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _body(payload: dict[str, Any]) -> str:
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        return _decode((payload.get("body") or {}).get("data"))
    if mime_type == "text/html":
        return _html_to_text(_decode((payload.get("body") or {}).get("data")))
    plain = ""
    html = ""
    for part in payload.get("parts") or []:
        content = _body(part)
        if not content:
            continue
        if part.get("mimeType") == "text/plain" and not plain:
            plain = content
        elif part.get("mimeType") == "text/html" and not html:
            html = content
        elif not plain:
            plain = content
    return plain or html or _decode((payload.get("body") or {}).get("data"))


def serialize_message(message: dict[str, Any], include_body: bool = False) -> dict[str, Any]:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []
    result = {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "cc": _header(headers, "Cc"),
        "subject": _header(headers, "Subject") or "(no subject)",
        "date": _header(headers, "Date"),
        "message_id": _header(headers, "Message-ID"),
        "snippet": message.get("snippet", ""),
        "labels": message.get("labelIds", []),
        "unread": "UNREAD" in message.get("labelIds", []),
    }
    if include_body:
        result["body"] = _body(payload)[:50000]
    return result


def list_messages(service, query: str = "in:inbox", limit: int = 10) -> dict[str, Any]:
    response = service.users().messages().list(
        userId="me", q=query, maxResults=max(1, min(limit, 50))
    ).execute()
    messages = []
    for item in response.get("messages", []):
        raw = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="metadata",
            metadataHeaders=["From", "To", "Cc", "Subject", "Date", "Message-ID"],
        ).execute()
        messages.append(serialize_message(raw))
    return {"query": query, "count": len(messages), "messages": messages}


def get_message(service, message_id: str) -> dict[str, Any]:
    raw = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    return serialize_message(raw, include_body=True)


def build_message(
    *,
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    recipients = {"to": addresses(to), "cc": addresses(cc), "bcc": addresses(bcc)}
    if not recipients["to"]:
        raise ValueError("At least one To address is required")
    message = EmailMessage()
    from_email = os.getenv("GMAIL_FROM_EMAIL", "").strip()
    if from_email:
        message["From"] = from_email
    message["To"] = ", ".join(recipients["to"])
    if recipients["cc"]:
        message["Cc"] = ", ".join(recipients["cc"])
    if recipients["bcc"]:
        message["Bcc"] = ", ".join(recipients["bcc"])
    message["Subject"] = subject.strip()
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    message.set_content(body)
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return {"raw": encoded}, {**recipients, "from": from_email}


def send_message(service, **kwargs) -> dict[str, Any]:
    thread_id = kwargs.pop("thread_id", None)
    raw, recipients = build_message(**kwargs)
    if thread_id:
        raw["threadId"] = thread_id
    sent = service.users().messages().send(userId="me", body=raw).execute()
    return {"status": "sent", "message": {"id": sent.get("id"), "thread_id": sent.get("threadId"), **recipients, "subject": kwargs["subject"]}}


def create_draft(service, **kwargs) -> dict[str, Any]:
    raw, recipients = build_message(**kwargs)
    draft = service.users().drafts().create(userId="me", body={"message": raw}).execute()
    return {"status": "drafted", "draft": {"id": draft.get("id"), "message_id": (draft.get("message") or {}).get("id"), **recipients, "subject": kwargs["subject"]}}


def reply_to_message(service, message_id: str, body: str, cc: str | None = None) -> dict[str, Any]:
    original = get_message(service, message_id)
    recipient = parseaddr(original["from"])[1]
    if not recipient:
        raise ValueError("The original sender address could not be resolved")
    subject = original["subject"]
    if not subject.casefold().startswith("re:"):
        subject = f"Re: {subject}"
    references = " ".join(part for part in [original.get("message_id"),] if part)
    return send_message(
        service,
        to=recipient,
        subject=subject,
        body=body,
        cc=cc,
        in_reply_to=original.get("message_id"),
        references=references,
        thread_id=original.get("thread_id"),
    )
