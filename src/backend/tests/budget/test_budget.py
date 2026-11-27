import datetime as dt
from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import add_tx, fake_market

NET_WORTH = "/api/budget/net-worth"
HOLDINGS = "/api/portfolio/holdings"
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


# --- Requirement: Monthly summary ---


def test_empty_month(auth_client):
    r = auth_client.get("/api/budget/2026-03")
    assert r.status_code == 200
    assert r.json() == {
        "month": "2026-03",
        "income": "0.00",
        "expenses": "0.00",
        "balance": "0.00",
        "surplus": "0.00",
        "by_category": [],
    }


def test_month_with_transactions(auth_client, db, user, category_id):
    food, tr = category_id("Jedzenie"), category_id("Transport")
    add_tx(db, user, date(2026, 3, 1), "3000.00", food)
    add_tx(db, user, date(2026, 3, 2), "-0.10", food)
    add_tx(db, user, date(2026, 3, 3), "-0.20", food)
    add_tx(db, user, date(2026, 3, 4), "-50.00", tr)
    add_tx(db, user, date(2026, 2, 28), "-999.00", tr)
    add_tx(db, user, date(2026, 4, 1), "-999.00", tr)
    body = auth_client.get("/api/budget/2026-03").json()
    assert body["income"] == "3000.00"
    assert body["expenses"] == "50.30"
    assert body["balance"] == "2949.70"
    assert body["surplus"] == "2949.70"
    assert body["by_category"] == [
        {"category_id": tr, "category_name": "Transport", "expenses": "50.00"},
        {"category_id": food, "category_name": "Jedzenie", "expenses": "0.30"},
    ]


def test_december_boundaries(auth_client, db, user, category_id):
    food = category_id("Jedzenie")
    add_tx(db, user, date(2026, 12, 31), "-1.00", food)
    add_tx(db, user, date(2027, 1, 1), "-100.00", food)
    assert auth_client.get("/api/budget/2026-12").json()["expenses"] == "1.00"


def test_deficit(auth_client, db, user, category_id):
    food = category_id("Jedzenie")
    add_tx(db, user, date(2026, 3, 1), "10.00", food)
    add_tx(db, user, date(2026, 3, 2), "-25.50", food)
    body = auth_client.get("/api/budget/2026-03").json()
    assert body["balance"] == "-15.50"
    assert body["surplus"] == "0.00"


def test_non_budget_categories_counted_but_not_in_surplus(auth_client, db, user, category_id):
    add_tx(db, user, date(2026, 3, 1), "-500.00", category_id("Inwestycje"))
    add_tx(db, user, date(2026, 3, 1), "500.00", category_id("Przelewy własne"))
    add_tx(db, user, date(2026, 3, 1), "-7.00", category_id("Jedzenie"))
    body = auth_client.get("/api/budget/2026-03").json()
    assert body["income"] == "500.00"
    assert body["expenses"] == "507.00"
    assert body["balance"] == "-7.00"
    assert body["surplus"] == "0.00"
    assert len(body["by_category"]) == 2


@pytest.mark.parametrize(
    "bad",
    ["2026-13", "2026-00", "2026-3", "abc", "202603", "2026-03-01"]
    + ["0000-05", "9999-12", "1899-12", "2100-01"],
)
def test_invalid_month_422(auth_client, bad):
    assert auth_client.get(f"/api/budget/{bad}").status_code == 422
    assert auth_client.get(f"/api/budget/{bad}/trend").status_code == 422


def test_summary_is_per_user(auth_client, other_auth_client, db, user, make_user, category_id):
    food = category_id("Jedzenie")
    add_tx(db, user, date(2026, 3, 1), "-10.00", food)
    add_tx(db, make_user(email="third@example.com"), date(2026, 3, 1), "-99.00", food)
    body = other_auth_client.get("/api/budget/2026-03").json()
    assert body["expenses"] == "0.00"
    assert body["by_category"] == []
    assert auth_client.get("/api/budget/2026-03").json()["expenses"] == "10.00"


# --- Requirement: Exact totals (N04); the property tests live in tests/analytics ---


def test_month_balances_sum_to_cash_balance(auth_client, db, user, category_id, monkeypatch):
    fake_market(monkeypatch)
    today = date.today()
    prev = today.replace(day=1) - dt.timedelta(days=1)
    add_tx(db, user, prev, "2000.00", category_id("Inne"))
    add_tx(db, user, prev, "-500.00", category_id("Inwestycje"))
    add_tx(db, user, today, "-40.25", category_id("Jedzenie"))
    add_tx(db, user, today, "100.00", category_id("Przelewy własne"))
    total = sum(
        Decimal(auth_client.get(f"/api/budget/{d:%Y-%m}").json()["balance"]) for d in (prev, today)
    )
    cash = Decimal(auth_client.get(NET_WORTH).json()["cash_balance"])
    assert total == cash == Decimal("1559.75")


# --- Requirement: Spending trend window ---


def test_trend_default_window_six_months_oldest_first(auth_client, db, user, category_id):
    add_tx(db, user, date(2026, 11, 3), "8500.00", category_id("Inne"))
    add_tx(db, user, date(2026, 11, 4), "-3712.16", category_id("Jedzenie"))
    r = auth_client.get("/api/budget/2026-11/trend")
    assert r.status_code == 200
    body = r.json()
    assert [m["month"] for m in body["months"]] == [f"2026-{n:02d}" for n in range(6, 12)]
    last = body["months"][-1]
    assert last["income"] == "8500.00"
    assert last["expenses"] == "3712.16"
    assert last["surplus"] == "4787.84"
    assert last["savings_rate"] == "56.3"


def test_trend_window_crosses_year(auth_client):
    body = auth_client.get("/api/budget/2026-01/trend?months=3").json()
    assert [m["month"] for m in body["months"]] == ["2025-11", "2025-12", "2026-01"]


@pytest.mark.parametrize("n", [3, 6, 12])
def test_trend_supported_windows(auth_client, n):
    body = auth_client.get(f"/api/budget/2026-11/trend?months={n}").json()
    assert len(body["months"]) == n


@pytest.mark.parametrize("n", ["4", "0", "13", "abc"])
def test_trend_unsupported_window_422(auth_client, n):
    assert auth_client.get(f"/api/budget/2026-11/trend?months={n}").status_code == 422


def test_trend_own_transfers_do_not_change_rate(auth_client, db, user, category_id):
    add_tx(db, user, date(2026, 11, 3), "8500.00", category_id("Inne"))
    add_tx(db, user, date(2026, 11, 4), "-3712.16", category_id("Jedzenie"))
    add_tx(db, user, date(2026, 11, 5), "1000.00", category_id("Przelewy własne"))
    add_tx(db, user, date(2026, 11, 5), "-1000.00", category_id("Przelewy własne"))
    last = auth_client.get("/api/budget/2026-11/trend").json()["months"][-1]
    assert last["income"] == "9500.00"
    assert last["surplus"] == "4787.84"
    assert last["savings_rate"] == "56.3"


def test_trend_savings_rate_null_without_budget_income(auth_client, db, user, category_id):
    add_tx(db, user, date(2026, 11, 3), "2000.00", category_id("Inwestycje"))
    last = auth_client.get("/api/budget/2026-11/trend").json()["months"][-1]
    assert last["income"] == "2000.00"
    assert last["savings_rate"] is None


def test_trend_average_change_and_categories(auth_client, db, user, category_id):
    food, tr = category_id("Jedzenie"), category_id("Transport")
    add_tx(db, user, date(2026, 8, 3), "-3000.00", food)
    add_tx(db, user, date(2026, 10, 3), "-5000.00", food)
    add_tx(db, user, date(2026, 11, 3), "-4400.00", food)
    add_tx(db, user, date(2026, 11, 4), "-20.00", tr)
    add_tx(db, user, date(2026, 11, 4), "-999.00", category_id("Inwestycje"))
    body = auth_client.get("/api/budget/2026-11/trend").json()
    assert body["average"]["expenses"] == "4000.00"
    assert body["change"]["expenses"] == {"amount": "1419.00", "pct": "35.5"}
    cats = {c["category_name"]: c for c in body["categories"]}
    assert "Inwestycje" not in cats
    assert [c["category_name"] for c in body["categories"]] == ["Jedzenie", "Transport"]
    assert cats["Jedzenie"]["amounts"] == ["0.00", "0.00", "3000.00", "0.00", "5000.00", "4400.00"]
    assert cats["Transport"]["average"] == "0.00"
    assert cats["Transport"]["change"] == "20.00"
    assert cats["Transport"]["change_pct"] is None


def test_trend_no_earlier_data_has_null_average(auth_client, db, user, category_id):
    add_tx(db, user, date(2026, 11, 3), "-10.00", category_id("Jedzenie"))
    body = auth_client.get("/api/budget/2026-11/trend").json()
    assert body["average"] is None
    assert body["change"] is None


def test_trend_is_per_user(auth_client, other_auth_client, db, user, make_user, category_id):
    food = category_id("Jedzenie")
    add_tx(db, user, date(2026, 11, 3), "-10.00", food)
    add_tx(db, make_user(email="third@example.com"), date(2026, 11, 3), "-99.00", food)
    mine = auth_client.get("/api/budget/2026-11/trend").json()
    theirs = other_auth_client.get("/api/budget/2026-11/trend").json()
    assert mine["months"][-1]["expenses"] == "10.00"
    assert theirs["months"][-1]["expenses"] == "0.00"
    assert theirs["categories"] == []


def test_trend_requires_session(client):
    assert client.get("/api/budget/2026-11/trend").status_code == 401


def test_insights_endpoint_removed(auth_client):
    assert auth_client.get("/api/budget/2026-03/insights").status_code == 404


# --- Requirement: Category limits (removed) ---


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_limits_endpoints_removed(auth_client, category_id, method):
    r = getattr(auth_client, method)(f"/api/budget/limits/{category_id('Jedzenie')}")
    assert r.status_code in (404, 405)
    assert auth_client.get("/api/budget/limits").status_code in (404, 405, 422)  # /{month}


# --- Requirement: Net worth ---


def test_net_worth_empty_is_zero(auth_client, monkeypatch):
    fake_market(monkeypatch)
    b = auth_client.get(NET_WORTH).json()
    assert b["cash_balance"] == b["portfolio_value"] == b["net_worth"] == "0.00"
    assert b["portfolio_complete"] is True
    assert b["as_of"] == dt.date.today().isoformat()


def test_net_worth_sums_until_today_and_is_per_user(
    auth_client, db, user, make_user, category_id, monkeypatch
):
    fake_market(monkeypatch, {"AAPL": "120.00"})
    cat = category_id("Inne")
    today = dt.date.today()
    add_tx(db, user, today, "1000.00", cat)
    add_tx(db, user, today - dt.timedelta(days=40), "-250.50", cat)
    add_tx(db, user, today + dt.timedelta(days=1), "999.00", cat)
    add_tx(db, make_user("o@example.com"), today, "5000.00", cat)
    auth_client.post(HOLDINGS, json=STOCK)
    auth_client.post(HOLDINGS, json=FLAT)
    b = auth_client.get(NET_WORTH).json()
    assert b["cash_balance"] == "749.50"
    assert b["portfolio_value"] == "501200.00"
    assert b["net_worth"] == "501949.50"
    assert b["portfolio_complete"] is True


def test_incomplete_valuation_when_market_down(auth_client, monkeypatch):
    fake_market(monkeypatch, fail=True)
    auth_client.post(HOLDINGS, json=STOCK)
    r = auth_client.get(NET_WORTH)
    assert r.status_code == 200
    assert r.json()["portfolio_complete"] is False
