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
    assert auth_client.get(f"/api/budget/{bad}/insights").status_code == 422


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


# --- Requirement: Month comparison and top growth ---


def test_insights_comparison_growth_and_limits(auth_client, db, user, category_id):
    food, tr = category_id("Jedzenie"), category_id("Transport")
    add_tx(db, user, date(2026, 3, 2), "-300.00", food)
    add_tx(db, user, date(2026, 3, 3), "-50.00", tr)
    add_tx(db, user, date(2026, 2, 3), "-100.00", food)
    add_tx(db, user, date(2026, 1, 3), "-100.00", food)
    add_tx(db, user, date(2025, 12, 3), "-100.00", food)
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "250.00"})
    auth_client.put(f"/api/budget/limits/{tr}", json={"amount": "250.00"})
    body = auth_client.get("/api/budget/2026-03/insights").json()
    assert body["previous_month"] == "2026-02"
    assert body["comparison"][0] == {
        "category_id": food,
        "category_name": "Jedzenie",
        "current": "300.00",
        "previous": "100.00",
        "change": "200.00",
        "change_pct": "200.0",
    }
    # previous month was zero
    assert body["comparison"][1]["category_name"] == "Transport"
    assert body["comparison"][1]["previous"] == "0.00"
    assert body["comparison"][1]["change_pct"] is None
    growth = {g["category_name"]: g for g in body["top_growth"]}
    assert growth["Jedzenie"]["average_3m"] == "100.00"
    assert growth["Transport"]["average_3m"] == "0.00"
    assert growth["Transport"]["increase_pct"] is None
    lim = {x["category_name"]: x for x in body["limits"]}
    assert lim["Jedzenie"]["exceeded"] is True and lim["Jedzenie"]["used_pct"] == "120.0"
    assert lim["Jedzenie"]["remaining"] == "-50.00"
    assert lim["Jedzenie"]["spent"] == "300.00" and lim["Jedzenie"]["limit"] == "250.00"
    assert lim["Transport"]["exceeded"] is False
    assert lim["Transport"]["remaining"] == "200.00"


def test_insights_fewer_than_three_prior_months_uses_available(auth_client, db, user, category_id):
    food = category_id("Jedzenie")
    add_tx(db, user, date(2025, 1, 5), "-60.00", food)  # only one earlier month has data
    add_tx(db, user, date(2025, 3, 5), "-90.00", food)
    [g] = auth_client.get("/api/budget/2025-03/insights").json()["top_growth"]
    assert g["average_3m"] == "20.00"  # (60 + 0 + 0) / 3: missing months count as zero
    assert g["increase"] == "70.00"
    assert g["increase_pct"] == "350.0"


def test_insights_empty_and_previous_month_crosses_year(auth_client):
    body = auth_client.get("/api/budget/2026-01/insights").json()
    assert body == {
        "month": "2026-01",
        "previous_month": "2025-12",
        "comparison": [],
        "top_growth": [],
        "limits": [],
    }


def test_insights_are_per_user(auth_client, other_auth_client, db, make_user, category_id):
    food = category_id("Jedzenie")
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "10.00"})
    add_tx(db, make_user(email="third@example.com"), date(2025, 3, 5), "-999.00", food)
    body = other_auth_client.get("/api/budget/2025-03/insights").json()
    assert body["comparison"] == [] and body["top_growth"] == [] and body["limits"] == []


# --- Requirement: Category limits ---


def test_limit_put_upsert_list_delete(auth_client, category_id):
    food, tr = category_id("Jedzenie"), category_id("Transport")
    r = auth_client.put(f"/api/budget/limits/{food}", json={"amount": "500.00"})
    assert r.status_code == 200
    assert r.json() == {"category_id": food, "category_name": "Jedzenie", "amount": "500.00"}
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "600.5"})
    auth_client.put(f"/api/budget/limits/{tr}", json={"amount": "999999999999.99"})
    items = auth_client.get("/api/budget/limits").json()
    assert [i["category_name"] for i in items] == ["Jedzenie", "Transport"]
    assert [i["amount"] for i in items] == ["600.50", "999999999999.99"]
    assert auth_client.delete(f"/api/budget/limits/{food}").status_code == 204
    assert len(auth_client.get("/api/budget/limits").json()) == 1


def test_limit_on_non_budget_category_422(auth_client, category_id):
    for name in ("Przelewy własne", "Inwestycje"):
        r = auth_client.put(f"/api/budget/limits/{category_id(name)}", json={"amount": "5"})
        assert r.status_code == 422
        assert r.json()["detail"] == "Limit można ustawić tylko dla kategorii budżetowej"


def test_limit_unknown_category_404(auth_client):
    r = auth_client.put("/api/budget/limits/999999", json={"amount": "5.00"})
    assert (r.status_code, r.json()["detail"]) == (404, "Nie znaleziono kategorii")


@pytest.mark.parametrize("amount", ["0", "-5.00", "10.123", "1000000000000.00", "abc", "", None])
def test_limit_invalid_amount_422(auth_client, category_id, amount):
    r = auth_client.put(f"/api/budget/limits/{category_id('Jedzenie')}", json={"amount": amount})
    assert r.status_code == 422


def test_removing_missing_limit_404(auth_client, category_id):
    r = auth_client.delete(f"/api/budget/limits/{category_id('Jedzenie')}")
    assert (r.status_code, r.json()["detail"]) == (404, "Nie ustawiono limitu dla tej kategorii")


def test_limits_are_per_user(auth_client, other_auth_client, category_id):
    food = category_id("Jedzenie")
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "500.00"})
    assert other_auth_client.get("/api/budget/limits").json() == []
    assert other_auth_client.delete(f"/api/budget/limits/{food}").status_code == 404
    other_auth_client.put(f"/api/budget/limits/{food}", json={"amount": "5.00"})
    assert [i["amount"] for i in auth_client.get("/api/budget/limits").json()] == ["500.00"]


def test_limit_exactly_reached_is_not_exceeded(auth_client, db, user, category_id):
    food = category_id("Jedzenie")
    add_tx(db, user, date(2025, 3, 5), "-100.00", food)
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "100.00"})
    [row] = auth_client.get("/api/budget/2025-03/insights").json()["limits"]
    assert row["exceeded"] is False and row["remaining"] == "0.00"


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
