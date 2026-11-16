import datetime as dt

from tests.portfolio.test_portfolio_api import BASE, fake_market


def test_prices_as_of_null_without_quotes(auth_client, monkeypatch):
    fake_market(monkeypatch, {})
    auth_client.post(
        BASE,
        json={
            "name": "Lokata",
            "asset_class": "cash",
            "quantity": "1",
            "purchase_price": "100.00",
            "manual_value": "100.00",
        },
    )
    body = auth_client.get("/api/portfolio/summary").json()
    assert body["prices_as_of"] is None
    assert body["holdings"][0]["as_of"] is None


def test_prices_as_of_present_with_quotes(auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": "120.00"})
    auth_client.post(
        BASE,
        json={
            "name": "Apple",
            "asset_class": "stock",
            "symbol": "AAPL",
            "quantity": "2",
            "purchase_price": "100.00",
        },
    )
    body = auth_client.get("/api/portfolio/summary").json()
    stamp = dt.datetime.fromisoformat(body["prices_as_of"])
    assert abs((dt.datetime.now(dt.UTC) - stamp).total_seconds()) < 60
    assert body["holdings"][0]["as_of"] == body["prices_as_of"]


def test_prices_as_of_is_oldest_of_quote_and_fx(auth_client, monkeypatch):
    import sys
    import types
    from decimal import Decimal

    from coffer.market.service import Quote
    from coffer.portfolio import service

    old = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    new = dt.datetime(2026, 1, 2, tzinfo=dt.UTC)
    mod = types.ModuleType("coffer.market.service")
    mod.get_quotes = lambda symbols, db=None: {  # type: ignore[attr-defined]
        "AAPL": Quote("AAPL", None, Decimal("10"), "USD", None, new)
    }
    mod.get_fx_quote = lambda a, b, db=None: (Decimal("4"), old)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, service.MARKET_SERVICE, mod)
    auth_client.post(
        BASE,
        json={
            "name": "Apple",
            "asset_class": "stock",
            "symbol": "AAPL",
            "quantity": "1",
            "purchase_price": "1.00",
        },
    )
    body = auth_client.get("/api/portfolio/summary").json()
    assert dt.datetime.fromisoformat(body["prices_as_of"]) == old
    assert dt.datetime.fromisoformat(body["holdings"][0]["as_of"]) == new
