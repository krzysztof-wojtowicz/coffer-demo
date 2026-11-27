from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.accounts.models import User
from coffer.analytics.month import TxView
from coffer.transactions import service
from coffer.transactions.models import Category, Transaction


def _post(client: TestClient, **kw):
    body = {"date": "2026-03-10", "amount": "-45.50", "description": "Zakupy"}
    body.update(kw)
    return client.post("/api/transactions", json=body)


# --- Requirement: Manual transaction entry ---


def test_create_basic(auth_client: TestClient, db: Session, category_id):
    cid = category_id("Inne")
    r = _post(auth_client, category_id=cid)
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == "-45.50"
    assert body["source"] == "manual"
    assert body["date"] == "2026-03-10"
    assert body["description"] == "Zakupy"
    assert body["category_id"] == cid
    assert body["category_name"] == "Inne"
    assert db.get(Transaction, body["id"]).amount == Decimal("-45.50")


def test_create_default_category(auth_client: TestClient, db: Session):
    r = _post(auth_client)
    assert r.status_code == 201
    default = db.scalars(select(Category).where(Category.is_default)).one()
    assert r.json()["category_id"] == default.id
    assert r.json()["category_name"] == default.name


def test_create_income_numeric_amount_and_trimmed_description(auth_client: TestClient):
    r = _post(auth_client, amount=100, description="  Kawa  ")
    assert r.status_code == 201
    assert r.json()["amount"] == "100.00"
    assert r.json()["description"] == "Kawa"
    assert _post(auth_client, amount=12.5).json()["amount"] == "12.50"


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"},
        {"amount": "1.005"},
        {"amount": "-1.005"},
        {"amount": "abc"},
        {"amount": "1000000000"},
        {"amount": "-1000000000"},
        {"amount": 1e30},
        {"amount": "1E+30"},
        {"amount": "-1e50"},
        {"description": ""},
        {"description": "   "},
        {"date": "nie-data"},
        {"date": None},
    ],
)
def test_create_validation_422(auth_client: TestClient, db: Session, overrides):
    assert _post(auth_client, **overrides).status_code == 422
    assert db.scalars(select(Transaction)).all() == []


def test_create_missing_fields_422(auth_client: TestClient):
    assert auth_client.post("/api/transactions", json={"amount": "1"}).status_code == 422
    body = {"amount": "1", "description": "x"}
    assert auth_client.post("/api/transactions", json=body).status_code == 422


def test_create_boundaries_ok(auth_client: TestClient):
    assert _post(auth_client, amount="999999999.99").status_code == 201
    assert _post(auth_client, amount="-999999999.99").status_code == 201
    assert _post(auth_client, amount="0.01").status_code == 201
    assert _post(auth_client, description="x" * 500).status_code == 201


def test_create_unknown_category(auth_client: TestClient):
    r = _post(auth_client, category_id=999999)
    assert r.status_code == 422
    assert r.json() == {"detail": "Nieznana kategoria"}


def test_cents_precision_roundtrip(auth_client: TestClient):
    _post(auth_client, amount="0.10", description="a")
    _post(auth_client, amount="0.20", description="b")
    amounts = sorted(t["amount"] for t in auth_client.get("/api/transactions").json())
    assert amounts == ["0.10", "0.20"]
    assert sum(Decimal(a) for a in amounts) == Decimal("0.30")


# --- Requirement: Categories ---


def test_categories_sorted_with_one_default(auth_client: TestClient):
    r = auth_client.get("/api/categories")
    assert r.status_code == 200
    cats = r.json()
    assert set(cats[0]) == {"id", "name", "in_budget", "is_default"}
    names = [c["name"] for c in cats]
    assert names == sorted(names)
    defaults = [c for c in cats if c["is_default"]]
    assert [c["name"] for c in defaults] == ["Inne"]
    out = {c["name"] for c in cats if not c["in_budget"]}
    assert {"Przelewy własne", "Inwestycje"} <= out


# --- Requirement: Listing transactions ---


def test_list_all_sorted_date_desc_then_id_desc(auth_client: TestClient):
    a = _post(auth_client, date="2026-03-01", description="a").json()["id"]
    b = _post(auth_client, date="2026-03-05", description="b").json()["id"]
    c = _post(auth_client, date="2026-03-05", description="c").json()["id"]
    d = _post(auth_client, date="2026-01-31", description="d").json()["id"]
    r = auth_client.get("/api/transactions")
    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == [c, b, a, d]


@pytest.mark.parametrize(
    ("month", "dates", "expected"),
    [
        ("2026-03", ["2026-02-28", "2026-03-01", "2026-03-31", "2026-04-01"], 2),
        ("2026-12", ["2026-12-31", "2027-01-01"], 1),
        ("2020-01", ["2026-03-01"], 0),
    ],
)
def test_list_month_filter(auth_client: TestClient, month, dates, expected):
    for i, d in enumerate(dates):
        _post(auth_client, date=d, description=f"t{i}")
    r = auth_client.get("/api/transactions", params={"month": month})
    assert r.status_code == 200
    assert len(r.json()) == expected
    assert all(t["date"].startswith(month) for t in r.json())


@pytest.mark.parametrize(
    "month", ["2026-13", "2026-00", "2026-3", "202603", "abc", "2026-03-01", "9999-12"]
)
def test_list_bad_month_422(auth_client: TestClient, month):
    assert auth_client.get("/api/transactions", params={"month": month}).status_code == 422


def test_list_isolation(auth_client: TestClient, other_auth_client: TestClient):
    mine = _post(auth_client, description="moja").json()["id"]
    theirs = _post(other_auth_client, description="cudza").json()["id"]
    assert [t["id"] for t in auth_client.get("/api/transactions").json()] == [mine]
    assert [t["id"] for t in other_auth_client.get("/api/transactions").json()] == [theirs]


# --- Requirement: Edit and delete ---


def test_update_all_fields(auth_client: TestClient, category_id):
    tid = _post(auth_client).json()["id"]
    cid = category_id("Inne")
    r = auth_client.patch(
        f"/api/transactions/{tid}",
        json={"date": "2026-04-01", "amount": "-10", "description": " Nowy ", "category_id": cid},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-04-01"
    assert body["amount"] == "-10.00"
    assert body["description"] == "Nowy"
    assert body["category_id"] == cid
    assert body["source"] == "manual"


def test_update_null_category_means_no_change(auth_client: TestClient, category_id):
    created = _post(auth_client, category_id=category_id("Inne")).json()
    r = auth_client.patch(
        f"/api/transactions/{created['id']}", json={"description": "X", "category_id": None}
    )
    assert r.status_code == 200
    assert r.json() == {**created, "description": "X"}


def test_update_ignores_source(auth_client: TestClient):
    tid = _post(auth_client).json()["id"]
    r = auth_client.patch(f"/api/transactions/{tid}", json={"source": "csv"})
    assert r.json()["source"] == "manual"


def test_update_unknown_category_422(auth_client: TestClient):
    tid = _post(auth_client).json()["id"]
    r = auth_client.patch(f"/api/transactions/{tid}", json={"category_id": 999999})
    assert r.status_code == 422
    assert r.json()["detail"] == "Nieznana kategoria"


@pytest.mark.parametrize(
    "body", [{"amount": "0"}, {"amount": "1.234"}, {"description": "  "}, {"date": "x"}]
)
def test_update_validation_like_create(auth_client: TestClient, body):
    tid = _post(auth_client).json()["id"]
    assert auth_client.patch(f"/api/transactions/{tid}", json=body).status_code == 422


def test_delete_ok(auth_client: TestClient):
    tid = _post(auth_client).json()["id"]
    assert auth_client.delete(f"/api/transactions/{tid}").status_code == 204
    assert auth_client.get("/api/transactions").json() == []
    assert auth_client.delete(f"/api/transactions/{tid}").status_code == 404


def test_missing_or_foreign_transaction_404_polish(
    auth_client: TestClient, other_auth_client: TestClient
):
    foreign = _post(other_auth_client).json()["id"]
    for tid in (foreign, 999999):
        for r in (
            auth_client.patch(f"/api/transactions/{tid}", json={"description": "x"}),
            auth_client.delete(f"/api/transactions/{tid}"),
        ):
            assert r.status_code == 404
            assert r.json() == {"detail": "Nie znaleziono transakcji"}
    listed = other_auth_client.get("/api/transactions").json()
    assert [t["description"] for t in listed] == ["Zakupy"]


# --- Service-level: views for analytics and learned-category hints ---


def _add(db, user, day, desc, cat, review=False, amount="-1.00"):
    db.add(
        Transaction(
            user_id=user.id,
            date=day,
            amount=Decimal(amount),
            description=desc,
            category_id=cat,
            source="manual",
            needs_review=review,
        )
    )
    db.commit()


def test_list_views_range_user_and_budget_flag(db: Session, user: User, make_user, category_id):
    other = make_user(email="o@example.com")
    non_budget = db.query(Category).filter(Category.in_budget.is_(False)).first()
    _add(db, user, date(2026, 2, 28), "a", category_id("Inne"))
    _add(db, user, date(2026, 3, 1), "b", category_id("Inne"), amount="-10.10")
    _add(db, user, date(2026, 3, 31), "c", non_budget.id, amount="20.20")
    _add(db, user, date(2026, 4, 1), "d", category_id("Inne"))
    _add(db, other, date(2026, 3, 15), "e", category_id("Inne"), amount="-99")
    views = service.list_views(db, user.id, date(2026, 3, 1), date(2026, 4, 1))
    assert all(isinstance(v, TxView) for v in views)
    assert {v.amount for v in views} == {Decimal("-10.10"), Decimal("20.20")}
    by_date = {v.date: v for v in views}
    assert by_date[date(2026, 3, 1)].category_name == "Inne"
    assert by_date[date(2026, 3, 1)].in_budget is True
    assert by_date[date(2026, 3, 31)].in_budget is False


def test_category_hints_newest_wins_and_skips_review(db, user, make_user, category_id):
    food, shop, other = category_id("Jedzenie"), category_id("Zakupy"), category_id("Inne")
    _add(db, user, date(2026, 1, 1), "Sklep  U Zosi", food)
    _add(db, user, date(2026, 2, 1), "SKLEP U ZOSI", shop)
    _add(db, user, date(2026, 3, 1), "SKLEP U ZOSI", other, review=True)
    stranger = make_user(email="x@example.com")
    _add(db, stranger, date(2026, 4, 1), "OBCY", food)
    assert service.category_hints(db, user.id) == {"sklep u zosi": "Zakupy"}
