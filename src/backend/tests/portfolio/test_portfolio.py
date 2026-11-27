"""Portfolio: holdings CRUD, validation, summary valuation, price date (N07)."""

import datetime as dt
from decimal import Decimal

import pytest

from coffer.market import service as market
from coffer.market.service import Quote
from coffer.portfolio import service
from tests.conftest import fake_market

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
HUGE = {
    "name": "Max",
    "asset_class": "cash",
    "quantity": "999999999999.99999999",
    "purchase_price": "999999999999.99",
}


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
        ({"purchase_price": "-5"}, "Cena zakupu nie może być ujemna"),
        ({"purchase_price": "1.234"}, "Cena zakupu: maksymalnie 2 miejsca"),
        ({"manual_value": "-1"}, "Wartość bieżąca nie może być ujemna"),
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


def test_summary_empty(auth_client, monkeypatch):
    fake_market(monkeypatch)
    s = auth_client.get("/api/portfolio/summary").json()
    assert s["holdings"] == [] and s["allocation"] == []
    assert s["total_value"] == "0.00"
    assert s["total_gain_pct"] is None


def test_summary_rounds_half_up(auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": "12.345"})
    auth_client.post(BASE, json={**STOCK, "quantity": "1"})
    h = auth_client.get("/api/portfolio/summary").json()["holdings"][0]
    assert h["market_price"] == "12.35"  # ROUND_HALF_UP, not half-even
    assert h["current_value"] == "12.35"


def test_summary_uses_manual_value_when_no_quotes(auth_client, monkeypatch):
    fake_market(monkeypatch)
    auth_client.post(BASE, json=FLAT)
    s = auth_client.get("/api/portfolio/summary").json()
    assert s["prices_available"] is True
    assert s["holdings"][0]["value_source"] == "manual"
    assert s["holdings"][0]["current_value"] == "500000.00"


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


def test_crypto_symbol_is_quoted_as_usd_pair_and_converted(auth_client, monkeypatch):
    # Bare "BTC"/"ETH" are ETFs on Yahoo (tens of USD); the bug valued 0.003 BTC at ~0.4 PLN.
    calls = fake_market(
        monkeypatch,
        {"BTC": ("31.62", "USD"), "BTC-USD": ("70000.00", "USD"), "ETH-USD": ("2000.00", "USD")},
        fx={"USD": Decimal("4")},
    )
    base = {"asset_class": "crypto", "purchase_price": "1000.00"}
    auth_client.post(BASE, json={**base, "name": "Bitcoin", "symbol": "btc", "quantity": "0.003"})
    auth_client.post(BASE, json={**base, "name": "Ether", "symbol": "ETH", "quantity": "0.1"})
    auth_client.post(BASE, json={**STOCK, "symbol": "BTC"})  # a stock named BTC stays as is
    btc, eth, stock = auth_client.get("/api/portfolio/summary").json()["holdings"]
    assert calls[0] == ["BTC", "BTC-USD", "ETH-USD"]
    assert btc["symbol"] == "BTC" and btc["price_currency"] == "USD"
    assert btc["value_source"] == "market" and btc["current_value"] == "840.00"
    assert eth["current_value"] == "800.00"
    assert stock["current_value"] == "1264.80"  # 10 * 31.62 * 4


def test_quote_ticker_mapping():
    assert service.quote_ticker("btc", "crypto") == "BTC-USD"
    assert service.quote_ticker("BTC-PLN", "crypto") == "BTC-PLN"
    assert service.quote_ticker("BTC", "etf") == "BTC"
    assert service.quote_ticker("AAPL", "stock") == "AAPL"


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
    old = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    new = dt.datetime(2026, 1, 2, tzinfo=dt.UTC)
    quotes = {"AAPL": Quote("AAPL", Decimal("10"), "USD", None, new)}
    monkeypatch.setattr(market, "get_quotes", lambda symbols, db=None: quotes)
    monkeypatch.setattr(market, "get_fx_quote", lambda a, b, db=None: (Decimal("4"), old))
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


def test_summary_survives_max_amounts(auth_client, monkeypatch):
    monkeypatch.setattr(service, "fetch_prices", lambda *a, **k: None)
    for _ in range(1000):  # 1000 x ~1e24 needs 30 digits > default Decimal precision (28)
        assert auth_client.post(BASE, json=HUGE).status_code == 201
    r = auth_client.get("/api/portfolio/summary")
    assert r.status_code == 200
    assert r.json()["total_cost"].startswith("99999999999")


# --- Target allocation and gap ---

PROFILE_ALL = {
    "horizon": "medium",
    "risk": "medium",
    "preferred_classes": ["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"],
}


def test_summary_target_null_without_profile(auth_client, monkeypatch):
    fake_market(monkeypatch)
    auth_client.post(BASE, json=FLAT)
    assert auth_client.get("/api/portfolio/summary").json()["target"] is None


def test_summary_target_with_gaps(auth_client, monkeypatch):
    fake_market(monkeypatch)
    auth_client.put("/api/profile", json=PROFILE_ALL)
    auth_client.post(BASE, json=FLAT)  # 100% real_estate, which is not in the target
    t = auth_client.get("/api/portfolio/summary").json()["target"]
    by = {c["asset_class"]: c for c in t["classes"]}
    assert by["real_estate"]["target_pct"] in (0, "0", "0.0")
    assert Decimal(str(by["real_estate"]["gap_pp"])) == Decimal("100")
    assert Decimal(str(by["etf"]["gap_pp"])) == Decimal("-34")
    assert Decimal(t["total_gap_pp"]) == Decimal("100")


def test_summary_target_empty_portfolio_gaps_null(auth_client, monkeypatch):
    fake_market(monkeypatch)
    auth_client.put("/api/profile", json=PROFILE_ALL)
    t = auth_client.get("/api/portfolio/summary").json()["target"]
    assert t["total_gap_pp"] is None
    assert {c["asset_class"]: c["target_pct"] for c in t["classes"]}.keys() == {
        "stock",
        "etf",
        "bond",
        "cash",
        "commodity",
    }
    assert all(c["gap_pp"] is None for c in t["classes"])


def test_summary_target_is_per_user(auth_client, other_auth_client, monkeypatch):
    fake_market(monkeypatch)
    auth_client.put("/api/profile", json=PROFILE_ALL)
    assert other_auth_client.get("/api/portfolio/summary").json()["target"] is None


def test_holding_rejects_unknown_asset_class(auth_client):
    assert auth_client.post(BASE, json={**STOCK, "asset_class": "deposit"}).status_code == 422


def test_summary_positions_group_by_ticker_case(auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": "120.00"})
    auth_client.post(BASE, json={**STOCK, "symbol": "aapl", "purchase_date": "2024-09-02"})
    auth_client.post(BASE, json={**STOCK, "symbol": " AAPL ", "purchase_date": "2024-03-01"})
    s = auth_client.get("/api/portfolio/summary").json()
    assert len(s["holdings"]) == 2
    assert len(s["positions"]) == 1
    p = s["positions"][0]
    assert p["symbol"] == "AAPL"
    assert p["quantity"] == "20"
    assert p["cost"] == "2000.00" and p["value"] == "2400.00"
    assert p["gain"] == "400.00" and p["gain_pct"] == "20.0"
    assert p["share_pct"] == "100.0" and p["avg_price"] == "100.00"
    assert [lot["purchase_date"] for lot in p["lots"]] == ["2024-03-01", "2024-09-02"]
    lot = p["lots"][0]
    assert lot["currency"] == "PLN" and lot["value_source"] == "market"
    for k in ("quantity", "purchase_price", "cost", "value", "gain", "gain_pct"):
        assert isinstance(lot[k], str)


def test_summary_positions_without_ticker_are_separate(auth_client, monkeypatch):
    fake_market(monkeypatch)
    auth_client.post(BASE, json=FLAT)
    auth_client.post(BASE, json={**FLAT, "name": "Garaż"})
    positions = auth_client.get("/api/portfolio/summary").json()["positions"]
    assert len(positions) == 2
    assert all(len(p["lots"]) == 1 for p in positions)


def test_summary_positions_foreign_lot_own_currency(auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": ("200.00", "USD")}, fx={"USD": Decimal("4")})
    auth_client.post(
        BASE, json={**STOCK, "quantity": "5", "purchase_price": "150.00", "currency": "USD"}
    )
    p = auth_client.get("/api/portfolio/summary").json()["positions"][0]
    lot = p["lots"][0]
    assert (lot["cost"], lot["value"], lot["gain"]) == ("750.00", "1000.00", "250.00")
    assert lot["gain_pct"] == "33.3" and lot["currency"] == "USD"
    assert p["value"] == "4000.00" and p["cost"] == "3000.00"


def test_summary_positions_fx_missing_nulls_totals(auth_client, monkeypatch):
    fake_market(monkeypatch, fx={})
    auth_client.post(BASE, json={**STOCK, "currency": "CHF"})
    p = auth_client.get("/api/portfolio/summary").json()["positions"][0]
    assert p["value"] is None and p["cost"] is None and p["avg_price"] is None
    assert p["lots"][0]["cost"] == "1000.00"


def test_summary_positions_are_per_user(auth_client, other_auth_client, monkeypatch):
    fake_market(monkeypatch, {"AAPL": "120.00"})
    auth_client.post(BASE, json=STOCK)
    other_auth_client.post(BASE, json={**STOCK, "quantity": "3"})
    mine = auth_client.get("/api/portfolio/summary").json()["positions"]
    theirs = other_auth_client.get("/api/portfolio/summary").json()["positions"]
    assert len(mine) == 1 and len(mine[0]["lots"]) == 1 and mine[0]["quantity"] == "10"
    assert len(theirs) == 1 and len(theirs[0]["lots"]) == 1 and theirs[0]["quantity"] == "3"
