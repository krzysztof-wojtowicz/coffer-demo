from datetime import date
from decimal import Decimal

import pytest

from coffer.transactions.models import Transaction


@pytest.fixture
def add_tx(db):
    def _add(user, day, amount, category_id, description="x"):
        db.add(
            Transaction(
                user_id=user.id,
                date=day,
                amount=Decimal(amount),
                currency="PLN",
                base_amount=Decimal(amount),
                description=description,
                category_id=category_id,
                source="manual",
            )
        )
        db.commit()

    return _add


def test_requires_auth(client):
    assert client.get("/api/budget/2026-03").status_code == 401


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "2026-3", "abc", "202603", "2026-03-01"])
def test_bad_month_422(auth_client, bad):
    assert auth_client.get(f"/api/budget/{bad}").status_code == 422


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


def test_summary(auth_client, user, add_tx, category_id):
    food, tr = category_id("Jedzenie"), category_id("Transport")
    add_tx(user, date(2026, 3, 1), "3000.00", food)
    add_tx(user, date(2026, 3, 2), "-0.10", food)
    add_tx(user, date(2026, 3, 3), "-0.20", food)
    add_tx(user, date(2026, 3, 4), "-50.00", tr)
    add_tx(user, date(2026, 2, 28), "-999.00", tr)
    add_tx(user, date(2026, 4, 1), "-999.00", tr)
    body = auth_client.get("/api/budget/2026-03").json()
    assert body["income"] == "3000.00"
    assert body["expenses"] == "50.30"
    assert body["balance"] == "2949.70"
    assert body["surplus"] == "2949.70"
    assert body["by_category"] == [
        {"category_id": tr, "category_name": "Transport", "expenses": "50.00"},
        {"category_id": food, "category_name": "Jedzenie", "expenses": "0.30"},
    ]


def test_deficit(auth_client, user, add_tx, category_id):
    food = category_id("Jedzenie")
    add_tx(user, date(2026, 3, 1), "10.00", food)
    add_tx(user, date(2026, 3, 2), "-25.50", food)
    body = auth_client.get("/api/budget/2026-03").json()
    assert body["balance"] == "-15.50"
    assert body["surplus"] == "0.00"


def test_non_budget_categories_excluded(auth_client, user, add_tx, category_id):
    add_tx(user, date(2026, 3, 1), "-500.00", category_id("Inwestycje"))
    add_tx(user, date(2026, 3, 1), "500.00", category_id("Przelewy własne"))
    add_tx(user, date(2026, 3, 1), "-7.00", category_id("Jedzenie"))
    body = auth_client.get("/api/budget/2026-03").json()
    assert body["income"] == "0.00"
    assert body["expenses"] == "7.00"
    assert len(body["by_category"]) == 1


def test_december_boundaries(auth_client, user, add_tx, category_id):
    food = category_id("Jedzenie")
    add_tx(user, date(2026, 12, 31), "-1.00", food)
    add_tx(user, date(2027, 1, 1), "-100.00", food)
    assert auth_client.get("/api/budget/2026-12").json()["expenses"] == "1.00"


def test_user_isolation(auth_client, other_auth_client, user, make_user, add_tx, category_id):
    food = category_id("Jedzenie")
    add_tx(user, date(2026, 3, 1), "-10.00", food)
    other = make_user(email="third@example.com")
    add_tx(other, date(2026, 3, 1), "-99.00", food)
    body = other_auth_client.get("/api/budget/2026-03").json()
    assert body["expenses"] == "0.00"
    assert body["by_category"] == []
    assert auth_client.get("/api/budget/2026-03").json()["expenses"] == "10.00"


def test_service_function(db, user, add_tx, category_id):
    from coffer.budget.service import month_summary

    add_tx(user, date(2026, 3, 1), "-12.34", category_id("Jedzenie"))
    s = month_summary(db, user.id, "2026-03")
    assert s.expenses == Decimal("12.34")
    assert s.month == "2026-03"


@pytest.mark.parametrize("month", ["0000-05", "9999-12", "1899-12", "2100-01"])
def test_out_of_range_month_is_422(auth_client, month):
    assert auth_client.get(f"/api/budget/{month}").status_code == 422
