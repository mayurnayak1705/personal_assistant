"""Live market-data lookup used by the finance watchlist.

Yahoo's public chart/search endpoints require no API key.  Keeping the HTTP
code in this small module makes it straightforward to replace with a licensed
feed later without changing storage, chat tools, or the UI.
"""
from __future__ import annotations

from typing import Any

import requests


SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "DeepThoughtPersonalAssistant/1.0"}
INDIA_ALIASES = {
    "reliance": ("RELIANCE.NS", "Reliance Industries Limited"),
    "relicance": ("RELIANCE.NS", "Reliance Industries Limited"),
    "reliance industries": ("RELIANCE.NS", "Reliance Industries Limited"),
}


def resolve_stock(query: str) -> dict[str, str]:
    """Resolve a natural company name or ticker to a tradable Yahoo symbol."""
    value = " ".join((query or "").strip().split())
    if not value:
        raise ValueError("Tell me the company name or stock symbol to track.")
    alias = INDIA_ALIASES.get(value.casefold())
    if alias:
        return {"symbol": alias[0], "name": alias[1], "exchange": "NSE"}

    # Explicit exchange-qualified tickers should not depend on search ranking.
    if "." in value and " " not in value:
        return {"symbol": value.upper(), "name": value.upper(), "exchange": ""}

    response = requests.get(
        SEARCH_URL,
        params={"q": value, "quotesCount": 8, "newsCount": 0},
        headers=HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    quotes = response.json().get("quotes") or []
    equities = [q for q in quotes if q.get("quoteType") in {"EQUITY", "ETF"}]
    if not equities:
        raise ValueError(f"I could not resolve a listed stock named {value!r}.")
    # Prefer Indian listings when the user supplies a company name common to
    # several exchanges; otherwise retain the provider's relevance ranking.
    match = next((q for q in equities if q.get("exchange") in {"NSI", "BSE"}), equities[0])
    return {
        "symbol": str(match["symbol"]).upper(),
        "name": str(match.get("longname") or match.get("shortname") or match["symbol"]),
        "exchange": str(match.get("exchDisp") or match.get("exchange") or ""),
    }


def get_quote(symbol: str) -> dict[str, Any]:
    """Return the latest quote plus exchange-session change information."""
    response = requests.get(
        CHART_URL.format(symbol=symbol),
        params={"interval": "1m", "range": "1d"},
        headers=HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    result = (response.json().get("chart", {}).get("result") or [None])[0]
    if not result:
        raise ValueError(f"No market quote is available for {symbol}.")
    meta = result.get("meta") or {}
    price = meta.get("regularMarketPrice")
    previous = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None:
        closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        price = next((item for item in reversed(closes) if item is not None), None)
    if price is None:
        raise ValueError(f"No current price is available for {symbol}.")
    change = float(price) - float(previous) if previous not in (None, 0) else 0.0
    percent = (change / float(previous) * 100) if previous not in (None, 0) else 0.0
    return {
        "symbol": symbol.upper(),
        "price": round(float(price), 2),
        "previous_close": round(float(previous), 2) if previous is not None else None,
        "change": round(change, 2),
        "change_percent": round(percent, 2),
        "currency": str(meta.get("currency") or ""),
        "market_state": str(meta.get("marketState") or "UNKNOWN"),
        "exchange_timezone": str(meta.get("exchangeTimezoneName") or ""),
        "as_of": meta.get("regularMarketTime"),
    }
