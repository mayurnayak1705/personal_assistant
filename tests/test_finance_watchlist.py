from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import uuid

from app.features.finance import market as finance_market
from app.features.finance import store as finance_store
import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_reliance_name_resolves_to_nse_without_network():
    stock = finance_market.resolve_stock("Reliance")
    assert stock["symbol"] == "RELIANCE.NS"
    assert stock["exchange"] == "NSE"
    assert finance_market.resolve_stock("relicance")["symbol"] == "RELIANCE.NS"


def test_alert_evaluation_preserves_units_and_direction():
    quote = {"price": 510, "change_percent": 5.2}
    assert finance_store._alert_triggered({"alert_kind":"percent_deviation", "alert_value":5}, quote)
    assert finance_store._alert_triggered({"alert_kind":"percent_up", "alert_value":5}, quote)
    assert not finance_store._alert_triggered({"alert_kind":"percent_down", "alert_value":5}, quote)
    assert finance_store._alert_triggered({"alert_kind":"price_above", "alert_value":500}, quote)
    assert not finance_store._alert_triggered({"alert_kind":"price_below", "alert_value":500}, quote)


def test_915_summary_orders_gainers_and_losers(monkeypatch):
    report = {
        "stocks": [
            {"symbol":"UP.NS", "quote":{"change_percent":2.5}, "alert_triggered":False},
            {"symbol":"DOWN.NS", "quote":{"change_percent":-3.0}, "alert_triggered":False},
        ]
    }
    monkeypatch.setattr(finance_store, "watchlist_report", lambda *_args, **_kwargs: report)
    now = datetime(2026, 7, 21, 9, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
    items = finance_store.notifications("local-user", now=now)
    daily = next(item for item in items if item["type"] == "daily")
    assert daily["id"] == "daily:2026-07-21"
    assert "Up: UP.NS +2.50%" in daily["message"]
    assert "Down: DOWN.NS -3.00%" in daily["message"]


def test_finance_ui_is_read_only_and_configuration_is_nlp():
    html = (ROOT / "templates/index.html").read_text()
    script = (ROOT / "static/js/app.js").read_text()
    planner = (ROOT / "app/agents/planner.py").read_text()
    assert 'id="financeBtn"' in html
    assert 'id="financeReport"' in html
    assert 'id="financeNotificationList"' in html
    assert "financeSetupForm" not in html
    assert "/api/finance/watchlist" in script
    assert "/api/finance/notifications" in script
    assert "entirely through natural conversation" in planner
    assert "9:15 AM Asia/Kolkata" in planner


@pytest.mark.integration
def test_finance_watchlist_database_round_trip():
    user_id = f"finance-{uuid.uuid4()}"
    try:
        added = finance_store.add_stock(user_id, "Reliance", "percent_deviation", 5)
        assert added["symbol"] == "RELIANCE.NS"
        listed = finance_store.list_stocks(user_id)
        assert len(listed) == 1
        assert float(listed[0]["alert_value"]) == 5
        updated = finance_store.set_alert(user_id, "RELIANCE.NS", "price_above", 1500)
        assert updated["alert_kind"] == "price_above"
    finally:
        try:
            finance_store.remove_stock(user_id, "RELIANCE.NS")
        except ValueError:
            pass
