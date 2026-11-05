import datetime as dt
import sys
import types
from dataclasses import dataclass
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from coffer.portfolio import service

BASE = "/api/portfolio/holdings"
STOCK = {
    "name": "Apple",
    "symbol": "aapl",
    "asset_class": "stock",
    "quantity": "10",
    "purchase_price": "100.00",
}
FLAT = {
    "name": "Mieszkanie",
    "asset_class": "real_estate",
    "quantity": "1",
    "purchase_price": "400000.00",
    "manual_value": "500000.00",
}


class MarketDataUnavailable(Exception):
    pass


@dataclass
class Quote:
    symbol: str
    name: str
    price: Decimal
    currency: str
    change_pct: Decimal | None
    as_of: dt.datetime


def fake_market(monkeypatch, prices=None, fail=False, fx=None):
    """prices: symbol -> "price" (PLN) or ("price", "CCY"); fx: CCY -> PLN rate.

    Without `fx` the fake module has no get_fx_rate at all (older market module).
    """
    mod = types.ModuleType("coffer.market.service")
    calls: list[list[str]] = []

    def get_quotes(symbols):
        calls.append(list(symbols))
        if fail:
            raise MarketDataUnavailable("down")
        now = dt.datetime.now(dt.UTC)
        out = {}
        for s, p in (prices or {}).items():
            price, ccy = p if isinstance(p, tuple) else (p, "PLN")
            if s in symbols:
                out[s] = Quote(s, s, Decimal(price), ccy, None, now)
        return out

    def get_fx_rate(from_ccy, to_ccy):
        assert to_ccy == "PLN"
        return Decimal("1") if from_ccy == to_ccy else (fx or {}).get(from_ccy)

    mod.get_quotes = get_quotes  # type: ignore[attr-defined]
    mod.MarketDataUnavailable = MarketDataUnavailable  # type: ignore[attr-defined]
    if fx is not None:
        mod.get_fx_rate = get_fx_rate  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, service.MARKET_SERVICE, mod)
    return calls


def no_market(monkeypatch):
    monkeypatch.setitem(sys.modules, service.MARKET_SERVICE, None)  # import -> ImportError


def test_create_and_list(auth_client):
    r = auth_client.post(BASE, json=STOCK)
    assert r.status_code == 201
    body = r.json()
    assert body["symbol"] == "AAPL"
    assert body["quantity"] == "10"
    assert body["purchase_price"] == "100.00"
    assert body["currency"] == "PLN"
    assert body["manual_value"] is None
    assert auth_client.get(BASE).json() == [body]


def test_patch_updates_and_clears_nullable(auth_client):
    hid = auth_client.post(BASE, json=FLAT).json()["id"]
    r = auth_client.patch(f"{BASE}/{hid}", json={"manual_value": "520000.50", "note": "Kraków"})
    assert r.status_code == 200
    assert r.json()["manual_value"] == "520000.50"
    assert r.json()["note"] == "Kraków"
    assert r.json()["name"] == "Mieszkanie"
    r = auth_client.patch(f"{BASE}/{hid}", json={"manual_value": None})
    assert r.json()["manual_value"] is None


def test_patch_cannot_null_required(auth_client):
    hid = auth_client.post(BASE, json=STOCK).json()["id"]
    r = auth_client.patch(f"{BASE}/{hid}", json={"quantity": None})
    assert r.status_code == 422
    assert "nie może być puste" in r.text


def test_delete(auth_client):
    hid = auth_client.post(BASE, json=STOCK).json()["id"]
    assert auth_client.delete(f"{BASE}/{hid}").status_code == 204
    assert auth_client.get(BASE).json() == []
    assert auth_client.delete(f"{BASE}/{hid}").status_code == 404


@pytest.mark.parametrize(
    ("patch", "msg"),
    [
        ({"quantity": "0"}, "Ilość musi być większa od zera"),
        ({"quantity": "-1"}, "Ilość musi być większa od zera"),
        ({"purchase_price": "-5"}, "nie może być ujemna"),
        ({"purchase_price": "1.234"}, "maksymalnie 2 miejsca"),
        ({"manual_value": "-1"}, "nie może być ujemna"),
        ({"currency": "ZŁOTY"}, "3-literowym"),
        ({"purchase_date": "2999-01-01"}, "z przyszłości"),
        ({"asset_class": "gold"}, ""),
        ({"name": "  "}, ""),
    ],
)
def test_validation_422(auth_client, patch, msg):
    r = auth_client.post(BASE, json={**STOCK, **patch})
    assert r.status_code == 422
    assert msg in r.text


@pytest.mark.parametrize("missing", ["name", "asset_class", "quantity", "purchase_price"])
def test_missing_required_422(auth_client, missing):
    body = {k: v for k, v in STOCK.items() if k != missing}
    assert auth_client.post(BASE, json=body).status_code == 422


def test_user_isolation_404(auth_client, other_auth_client):
    hid = auth_client.post(BASE, json=STOCK).json()["id"]
    assert other_auth_client.get(BASE).json() == []
    assert other_auth_client.patch(f"{BASE}/{hid}", json={"name": "X"}).status_code == 404
    assert other_auth_client.delete(f"{BASE}/{hid}").status_code == 404
    no_summary = other_auth_client.get("/api/portfolio/summary").json()
    assert no_summary["holdings"] == []
    assert auth_client.get(BASE).json()[0]["name"] == "Apple"


def test_requires_auth(client: TestClient):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=STOCK).status_code == 401
    assert client.patch(f"{BASE}/1", json={}).status_code == 401
    assert client.delete(f"{BASE}/1").status_code == 401
    assert client.get("/api/portfolio/summary").status_code == 401


def test_summary_with_market_prices(auth_client, monkeypatch):
    calls = fake_market(monkeypatch, {"AAPL": "120.00"})
    auth_client.post(BASE, json=STOCK)
    auth_client.post(BASE, json=FLAT)
    s = auth_client.get("/api/portfolio/summary").json()
    assert calls == [["AAPL"]]
    assert s["prices_available"] is True
    stock, flat = s["holdings"]
    assert stock["value_source"] == "market"
    assert stock["market_price"] == "120.00"
    assert stock["current_value"] == "1200.00"
    assert stock["gain"] == "200.00"
    assert stock["gain_pct"] == "20.0"
    assert flat["value_source"] == "manual"
    assert flat["current_value"] == "500000.00"
    assert flat["gain_pct"] == "25.0"
    assert s["total_value"] == "501200.00"
    assert s["total_cost"] == "401000.00"
    assert s["total_gain"] == "100200.00"
    assert [a["asset_class"] for a in s["allocation"]] == ["real_estate", "stock"]
    assert s["allocation"][0]["share_pct"] == "99.8"


def test_summary_market_unavailable(auth_client, monkeypatch):
    fake_market(monkeypatch, fail=True)
    auth_client.post(BASE, json=STOCK)
    s = auth_client.get("/api/portfolio/summary").json()
    assert s["prices_available"] is False
    assert s["holdings"][0]["value_source"] == "cost"
    assert s["holdings"][0]["current_value"] == "1000.00"
    assert s["total_gain"] == "0.00"


def test_summary_without_market_module(auth_client, monkeypatch):
    no_market(monkeypatch)
    auth_client.post(BASE, json=FLAT)
    s = auth_client.get("/api/portfolio/summary").json()
    assert s["prices_available"] is False
    assert s["holdings"][0]["value_source"] == "manual"
    assert s["total_value"] == "500000.00"


def test_summary_empty(auth_client, monkeypatch):
    no_market(monkeypatch)
    s = auth_client.get("/api/portfolio/summary").json()
    assert s["holdings"] == [] and s["allocation"] == []
    assert s["total_value"] == "0.00"
    assert s["total_gain_pct"] is None


def test_summary_converts_usd_to_pln(auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": ("200.00", "USD")}, fx={"USD": Decimal("4")})
    auth_client.post(BASE, json={**STOCK, "quantity": "2", "purchase_price": "700.00"})
    auth_client.post(BASE, json={**STOCK, "symbol": None, "name": "Gotówka USD",
                                 "asset_class": "cash", "quantity": "1",
                                 "purchase_price": "100.00", "currency": "USD"})  # fmt: skip
    s = auth_client.get("/api/portfolio/summary").json()
    stock, cash = s["holdings"]
    assert stock["value_source"] == "market"
    assert stock["current_value"] == "1600.00"
    assert stock["price_currency"] == "USD"
    assert stock["amount_currency"] == "PLN"
    assert cash["current_value"] == "400.00" and cash["cost_basis"] == "400.00"
    assert s["total_value"] == "2000.00"
    assert s["total_cost"] == "1800.00"
    assert s["fx_missing"] == []
    assert all(isinstance(s[k], str) for k in ("total_value", "total_cost", "total_gain"))


def test_summary_fx_missing_falls_back(auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": ("200.00", "USD")}, fx={})
    auth_client.post(BASE, json=STOCK)
    s = auth_client.get("/api/portfolio/summary").json()
    assert s["prices_available"] is True
    assert s["holdings"][0]["value_source"] == "cost"
    assert s["holdings"][0]["current_value"] == "1000.00"
    assert s["fx_missing"] == ["USD"]


def test_summary_without_fx_function(auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": ("200.00", "USD")})  # module lacks get_fx_rate
    auth_client.post(BASE, json=FLAT)
    auth_client.post(BASE, json=STOCK)
    s = auth_client.get("/api/portfolio/summary").json()
    assert s["fx_missing"] == ["USD"]
    assert s["total_value"] == "501000.00"
