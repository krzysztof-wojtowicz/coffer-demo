import datetime as dt
from decimal import Decimal

from coffer.transactions.models import Transaction
from tests.portfolio.test_portfolio_api import BASE, FLAT, STOCK, fake_market

URL = "/api/budget/net-worth"


def add_tx(db, user, day, amount, category_id):
    db.add(
        Transaction(
            user_id=user.id,
            date=day,
            amount=Decimal(amount),
            currency="PLN",
            base_amount=Decimal(amount),
            description="x",
            category_id=category_id,
            source="manual",
        )
    )
    db.commit()


def test_requires_auth(client):
    assert client.get(URL).status_code == 401


def test_empty_is_zero(auth_client, monkeypatch):
    fake_market(monkeypatch, {})
    r = auth_client.get(URL)
    assert r.status_code == 200
    b = r.json()
    assert b["cash_balance"] == b["portfolio_value"] == b["net_worth"] == "0.00"
    assert b["portfolio_complete"] is True
    assert b["as_of"] == dt.date.today().isoformat()


def test_sums_until_today_and_user_isolation(
    auth_client, db, user, make_user, category_id, monkeypatch
):
    fake_market(monkeypatch, {"AAPL": "120.00"})
    cat = category_id("Inne")
    today = dt.date.today()
    add_tx(db, user, today, "1000.00", cat)
    add_tx(db, user, today - dt.timedelta(days=40), "-250.50", cat)
    add_tx(db, user, today + dt.timedelta(days=1), "999.00", cat)
    add_tx(db, make_user("o@example.com"), today, "5000.00", cat)
    auth_client.post(BASE, json=STOCK)
    auth_client.post(BASE, json=FLAT)
    b = auth_client.get(URL).json()
    assert b["cash_balance"] == "749.50"
    assert b["portfolio_value"] == "501200.00"
    assert b["net_worth"] == "501949.50"
    assert b["portfolio_complete"] is True


def test_market_failure_is_incomplete_not_500(auth_client, monkeypatch):
    fake_market(monkeypatch, fail=True)
    auth_client.post(BASE, json=STOCK)
    r = auth_client.get(URL)
    assert r.status_code == 200
    assert r.json()["portfolio_complete"] is False
