"""Conservatively import confirmed Indian-bank debit emails as expenses."""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from mcp_servers.gmail.auth import gmail_service
from mcp_servers.gmail.messages import get_message
from debug_log import debug


DB_PATH = Path(os.getenv("EXPENSE_DB_PATH", Path(__file__).parent / "mcp_servers/expense/server/expenses.db"))
BANK_MARKERS = {
    "hdfc", "icici", "sbi", "state bank of india", "axis bank", "kotak", "indusind",
    "yes bank", "idfc", "au small finance", "federal bank", "canara bank",
    "punjab national bank", "pnb", "bank of baroda", "union bank", "indian bank",
    "rbl", "bandhan bank", "dbs bank", "hsbc", "standard chartered", "citibank",
    "amex", "american express",
}
IGNORE_MARKERS = {
    "otp", "one time password", "refund", "refunded", "reversal", "reversed", "declined",
    "failed", "unsuccessful", "could not be processed", "credited", "credit alert",
    "cashback", "reward points", "statement is ready",
}
DEBIT_MARKERS = {
    "debited", "debit card", "spent", "purchase", "paid", "payment of", "transaction of",
    "withdrawn", "withdrawal", "upi transaction",
}
AMOUNT_PATTERNS = (
    re.compile(r"(?:debited|spent|paid|purchase(?:\s+of)?|payment(?:\s+of)?|withdrawn|transaction(?:\s+of)?)[^₹\n\r]{0,45}(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)", re.I),
    re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)[^\n\r]{0,55}(?:debited|spent|paid|purchase|payment|withdrawn)", re.I),
)
MERCHANT_PATTERNS = (
    re.compile(r"(?:at|to|towards|merchant)\s+([A-Za-z0-9][A-Za-z0-9 &._'/-]{2,60})", re.I),
    re.compile(r"(?:info|remark|description)[:\s-]+([A-Za-z0-9][A-Za-z0-9 &._'/-]{2,60})", re.I),
)
def init_schema() -> None:
    debug("DB", "connect", engine="sqlite", database=str(DB_PATH), integration="gmail_expense_import")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL, amount REAL NOT NULL, category TEXT NOT NULL,
                subcategory TEXT DEFAULT '', note TEXT DEFAULT ''
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS expense_email_imports(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gmail_message_id TEXT NOT NULL UNIQUE,
                expense_id INTEGER, bank_name TEXT, merchant TEXT, amount REAL NOT NULL,
                transaction_date TEXT NOT NULL, category TEXT,
                suggested_category TEXT,
                status TEXT NOT NULL DEFAULT 'pending', subject TEXT, sender TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP, resolved_at DATETIME
            )
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(expense_email_imports)")}
        if "suggested_category" not in columns:
            connection.execute("ALTER TABLE expense_email_imports ADD COLUMN suggested_category TEXT")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS expense_email_scans(
                gmail_message_id TEXT PRIMARY KEY,
                scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _bank_name(text: str) -> str | None:
    lowered = text.casefold()
    compact = re.sub(r"[^a-z0-9]", "", lowered)
    marker = next((
        item for item in BANK_MARKERS
        if item in lowered or re.sub(r"[^a-z0-9]", "", item) in compact
    ), None)
    return marker.upper() if marker and len(marker) <= 4 else marker.title() if marker else None


def _amount(text: str) -> float | None:
    values = []
    for pattern in AMOUNT_PATTERNS:
        for match in pattern.finditer(text):
            try:
                value = float(match.group(1).replace(",", ""))
            except ValueError:
                continue
            if value > 0:
                values.append(value)
    unique = list(dict.fromkeys(values))
    return unique[0] if len(unique) == 1 else None


def _merchant(text: str) -> str:
    for pattern in MERCHANT_PATTERNS:
        match = pattern.search(text)
        if match:
            value = re.split(r"\s+(?:on|using|via|ref|reference|avl|available)\b", match.group(1), maxsplit=1, flags=re.I)[0]
            return value.strip(" .,-")[:80]
    return "Bank transaction"


def parse_transaction_email(email: dict[str, Any]) -> dict[str, Any] | None:
    sender, subject, body = (str(email.get(key) or "") for key in ("from", "subject", "body"))
    text = f"{sender}\n{subject}\n{body}"
    lowered = text.casefold()
    bank = _bank_name(f"{sender} {subject}")
    if not bank or any(marker in lowered for marker in IGNORE_MARKERS):
        return None
    if not any(marker in lowered for marker in DEBIT_MARKERS):
        return None
    amount = _amount(text)
    if amount is None:
        return None
    merchant = _merchant(text)
    try:
        transaction_date = parsedate_to_datetime(email.get("date", "")).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        transaction_date = datetime.now().date().isoformat()
    return {
        "gmail_message_id": str(email["id"]), "bank_name": bank, "merchant": merchant,
        "amount": amount, "transaction_date": transaction_date,
        "category": None, "subject": subject[:500], "sender": sender[:500],
    }


def _insert_candidate(candidate: dict[str, Any]) -> bool:
    init_schema()
    with sqlite3.connect(DB_PATH) as connection:
        if connection.execute("SELECT 1 FROM expense_email_imports WHERE gmail_message_id = ?", (candidate["gmail_message_id"],)).fetchone():
            return False
        learned = connection.execute("""
            SELECT category FROM expense_email_imports
            WHERE LOWER(merchant) = LOWER(?) AND category IS NOT NULL AND status = 'kept'
            ORDER BY resolved_at DESC, id DESC LIMIT 1
        """, (candidate["merchant"],)).fetchone()
        suggested_category = learned[0] if learned else None
        note = f"Imported from {candidate['bank_name']} email · {candidate['merchant']}"
        cursor = connection.execute(
            "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?, ?, ?, '', ?)",
            (candidate["transaction_date"], candidate["amount"], "misc", note),
        )
        connection.execute("""
            INSERT INTO expense_email_imports(gmail_message_id, expense_id, bank_name, merchant,
                amount, transaction_date, category, suggested_category, status, subject, sender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (candidate["gmail_message_id"], cursor.lastrowid, candidate["bank_name"],
              candidate["merchant"], candidate["amount"], candidate["transaction_date"],
              None, suggested_category, "needs_category",
              candidate["subject"], candidate["sender"]))
        return True


def scan_transaction_emails(limit: int = 25) -> dict[str, Any]:
    init_schema()
    service = gmail_service()
    query = 'newer_than:3d (debited OR spent OR "payment of" OR purchase OR withdrawn)'
    debug("TOOL", "call", integration="gmail", tool="search_transaction_emails",
          parameters={"query": query, "limit": limit})
    response = service.users().messages().list(userId="me", q=query, maxResults=max(1, min(limit, 50))).execute()
    imported = examined = 0
    for item in response.get("messages", []):
        message_id = item.get("id")
        if not message_id:
            continue
        with sqlite3.connect(DB_PATH) as connection:
            already_scanned = connection.execute(
                "SELECT 1 FROM expense_email_scans WHERE gmail_message_id = ?", (message_id,)
            ).fetchone()
            already_imported = connection.execute(
                "SELECT 1 FROM expense_email_imports WHERE gmail_message_id = ?", (message_id,)
            ).fetchone()
            if already_scanned or already_imported:
                continue
        examined += 1
        candidate = parse_transaction_email(get_message(service, message_id))
        if candidate and _insert_candidate(candidate):
            imported += 1
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO expense_email_scans(gmail_message_id) VALUES (?)",
                (message_id,),
            )
    result = {"status": "ok", "examined": examined, "imported": imported}
    debug("TOOL", "result", integration="gmail", tool="search_transaction_emails", **result)
    return result


IMPORT_COLUMNS = ("id", "gmail_message_id", "expense_id", "bank_name", "merchant", "amount", "transaction_date", "category", "suggested_category", "status", "subject", "sender", "created_at")


def pending_imports(limit: int = 50) -> list[dict[str, Any]]:
    init_schema()
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            f"SELECT {', '.join(IMPORT_COLUMNS)} FROM expense_email_imports WHERE status IN ('pending', 'needs_category') ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [dict(zip(IMPORT_COLUMNS, row)) for row in rows]


def resolve_import(import_id: int, action: str, category: str | None = None) -> dict[str, Any] | None:
    init_schema()
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM expense_email_imports WHERE id = ? AND status IN ('pending', 'needs_category')", (import_id,)).fetchone()
        if not row:
            return None
        if action == "delete":
            connection.execute("DELETE FROM expenses WHERE id = ?", (row["expense_id"],))
            status = "deleted"
        elif action == "keep":
            status = "kept"
        elif action == "categorize" and category:
            connection.execute("UPDATE expenses SET category = ? WHERE id = ?", (category, row["expense_id"]))
            connection.execute("UPDATE expense_email_imports SET category = ? WHERE id = ?", (category, import_id))
            status = "kept"
        else:
            raise ValueError("Use keep, delete, or categorize with a category")
        connection.execute("UPDATE expense_email_imports SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?", (status, import_id))
        return {"status": status, "import_id": import_id, "expense_id": row["expense_id"], "category": category or row["category"]}
