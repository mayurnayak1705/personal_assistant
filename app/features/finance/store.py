"""PostgreSQL persistence and alert evaluation for stock watchlists."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.persistence.postgres_insert import get_connection
from app.features.finance.market import get_quote, resolve_stock


ALERT_KINDS = {"percent_up", "percent_down", "percent_deviation", "price_above", "price_below"}


def init_finance_schema() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS finance_watchlist(
          id bigserial PRIMARY KEY, user_id varchar NOT NULL, symbol varchar(32) NOT NULL,
          company_name text NOT NULL, exchange varchar(40), alert_kind varchar(30),
          alert_value numeric, currency varchar(12), created_at timestamptz DEFAULT now(),
          updated_at timestamptz DEFAULT now(), UNIQUE(user_id, symbol));
        CREATE TABLE IF NOT EXISTS finance_quote_snapshots(
          id bigserial PRIMARY KEY, user_id varchar NOT NULL, symbol varchar(32) NOT NULL,
          price numeric NOT NULL, change_percent numeric NOT NULL, captured_at timestamptz DEFAULT now());
        CREATE INDEX IF NOT EXISTS finance_watchlist_user ON finance_watchlist(user_id, created_at);
        CREATE INDEX IF NOT EXISTS finance_quotes_user_symbol ON finance_quote_snapshots(user_id, symbol, captured_at DESC);
        """)
        conn.commit()


def _row_dict(row: Any) -> dict | None:
    return dict(row) if row else None


def add_stock(user_id: str, query: str, alert_kind: str | None = None,
              alert_value: float | None = None) -> dict:
    if alert_kind and alert_kind not in ALERT_KINDS:
        raise ValueError("Unsupported stock alert type.")
    if alert_kind and (alert_value is None or float(alert_value) < 0):
        raise ValueError("The alert needs a non-negative threshold.")
    stock = resolve_stock(query)
    init_finance_schema()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
          INSERT INTO finance_watchlist(user_id,symbol,company_name,exchange,alert_kind,alert_value)
          VALUES(%s,%s,%s,%s,%s,%s)
          ON CONFLICT(user_id,symbol) DO UPDATE SET
            company_name=EXCLUDED.company_name, exchange=EXCLUDED.exchange,
            alert_kind=COALESCE(EXCLUDED.alert_kind,finance_watchlist.alert_kind),
            alert_value=COALESCE(EXCLUDED.alert_value,finance_watchlist.alert_value), updated_at=now()
          RETURNING *
        """, (user_id, stock["symbol"], stock["name"], stock["exchange"], alert_kind, alert_value))
        row = cur.fetchone(); conn.commit()
    return dict(row)


def list_stocks(user_id: str) -> list[dict]:
    init_finance_schema()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM finance_watchlist WHERE user_id=%s ORDER BY created_at", (user_id,))
        return [dict(row) for row in cur.fetchall()]


def remove_stock(user_id: str, query: str) -> dict:
    value = (query or "").strip()
    init_finance_schema()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""DELETE FROM finance_watchlist WHERE user_id=%s AND
          (upper(symbol)=upper(%s) OR lower(company_name) LIKE lower(%s)) RETURNING *""",
                    (user_id, value, f"%{value}%"))
        rows = cur.fetchall()
        if len(rows) > 1:
            conn.rollback(); raise ValueError("More than one watchlist stock matches that name; use its ticker.")
        conn.commit()
    if not rows:
        raise ValueError(f"{value!r} is not in your watchlist.")
    return dict(rows[0])


def set_alert(user_id: str, query: str, alert_kind: str | None, alert_value: float | None) -> dict:
    if alert_kind is not None and alert_kind not in ALERT_KINDS:
        raise ValueError("Unsupported stock alert type.")
    if alert_kind is not None and (alert_value is None or float(alert_value) < 0):
        raise ValueError("The alert needs a non-negative threshold.")
    value = (query or "").strip()
    init_finance_schema()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE finance_watchlist SET alert_kind=%s,alert_value=%s,updated_at=now()
          WHERE user_id=%s AND (upper(symbol)=upper(%s) OR lower(company_name) LIKE lower(%s)) RETURNING *""",
                    (alert_kind, alert_value, user_id, value, f"%{value}%"))
        rows = cur.fetchall()
        if len(rows) > 1:
            conn.rollback(); raise ValueError("More than one watchlist stock matches that name; use its ticker.")
        conn.commit()
    if not rows:
        raise ValueError(f"{value!r} is not in your watchlist.")
    return dict(rows[0])


def _alert_triggered(stock: dict, quote: dict) -> bool:
    kind, raw = stock.get("alert_kind"), stock.get("alert_value")
    if not kind or raw is None:
        return False
    limit, change, price = float(raw), float(quote["change_percent"]), float(quote["price"])
    return {
        "percent_up": change >= limit,
        "percent_down": change <= -limit,
        "percent_deviation": abs(change) >= limit,
        "price_above": price >= limit,
        "price_below": price <= limit,
    }[kind]


def watchlist_report(user_id: str, quote_fetcher: Callable[[str], dict] = get_quote) -> dict:
    stocks = list_stocks(user_id)
    items, errors = [], []
    for stock in stocks:
        try:
            quote = quote_fetcher(stock["symbol"])
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("""INSERT INTO finance_quote_snapshots(user_id,symbol,price,change_percent)
                  VALUES(%s,%s,%s,%s)""", (user_id, stock["symbol"], quote["price"], quote["change_percent"]))
                conn.commit()
            items.append({**stock, "quote": quote, "alert_triggered": _alert_triggered(stock, quote)})
        except Exception as exc:
            errors.append({"symbol": stock["symbol"], "error": str(exc)})
            items.append({**stock, "quote": None, "alert_triggered": False})
    return {"stocks": items, "errors": errors, "count": len(items)}


def notifications(user_id: str, now: datetime | None = None,
                  quote_fetcher: Callable[[str], dict] = get_quote) -> list[dict]:
    now = now or datetime.now(ZoneInfo("Asia/Kolkata"))
    report = watchlist_report(user_id, quote_fetcher)
    alerts = []
    for item in report["stocks"]:
        quote = item.get("quote")
        if not quote or not item["alert_triggered"]:
            continue
        alerts.append({
            "id": f"threshold:{now.date()}:{item['symbol']}:{item['alert_kind']}:{item['alert_value']}",
            "type": "threshold", "title": f"{item['symbol']} stock alert",
            "message": f"{item['company_name']} is at {quote['price']} {quote['currency']} ({quote['change_percent']:+.2f}% today).",
        })
    if now.time() >= time(9, 15) and report["stocks"]:
        quoted = [item for item in report["stocks"] if item.get("quote")]
        if quoted:
            ordered = sorted(quoted, key=lambda item: item["quote"]["change_percent"], reverse=True)
            gainers = [f"{x['symbol']} {x['quote']['change_percent']:+.2f}%" for x in ordered if x["quote"]["change_percent"] > 0]
            losers = [f"{x['symbol']} {x['quote']['change_percent']:+.2f}%" for x in reversed(ordered) if x["quote"]["change_percent"] < 0]
            flat = [x["symbol"] for x in ordered if x["quote"]["change_percent"] == 0]
            parts = []
            if gainers: parts.append("Up: " + ", ".join(gainers))
            if losers: parts.append("Down: " + ", ".join(losers))
            if flat: parts.append("Unchanged: " + ", ".join(flat))
            alerts.append({
                "id": f"daily:{now.date()}", "type": "daily", "title": "9:15 AM stock update",
                "message": " · ".join(parts) or "No price movement is available yet.",
            })
    return alerts
