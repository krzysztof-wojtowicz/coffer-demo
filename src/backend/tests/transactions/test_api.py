from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.transactions.models import Category, Transaction


def _post(client: TestClient, **kw):
    body = {"date": "2026-03-10", "amount": "-45.50", "description": "Zakupy"}
    body.update(kw)
    return client.post("/api/transactions", json=body)


def test_endpoints_require_login(client: TestClient):
    assert client.get("/api/categories").status_code == 401
    assert client.get("/api/transactions").status_code == 401
    assert client.post("/api/transactions", json={}).status_code == 401
    assert client.delete("/api/transactions/1").status_code == 401


def test_categories_sorted_with_one_default(auth_client: TestClient):
    r = auth_client.get("/api/categories")
    assert r.status_code == 200
    cats = r.json()
    assert cats
    assert set(cats[0]) == {"id", "name", "in_budget", "is_default"}
    names = [c["name"] for c in cats]
    assert names == sorted(names)
    defaults = [c for c in cats if c["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "Inne"


def test_create_basic(auth_client: TestClient, category_id):
    cid = category_id("Inne")
    r = _post(auth_client, category_id=cid)
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == "-45.50"
    assert body["currency"] == "PLN"
    assert body["source"] == "manual"
    assert body["date"] == "2026-03-10"
    assert body["description"] == "Zakupy"
    assert body["category_id"] == cid
    assert body["category_name"] == "Inne"
    assert isinstance(body["id"], int)


def test_create_stores_base_amount(auth_client: TestClient, db: Session):
    r = _post(auth_client, amount="-12.34")
    tx = db.get(Transaction, r.json()["id"])
    assert tx.base_amount == Decimal("-12.34")
    assert tx.amount == Decimal("-12.34")
    assert tx.currency == "PLN"
    assert tx.source == "manual"


def test_create_default_category(auth_client: TestClient, db: Session):
    r = _post(auth_client)
    assert r.status_code == 201
    default = db.scalars(select(Category).where(Category.is_default)).one()
    assert r.json()["category_id"] == default.id
    assert r.json()["category_name"] == default.name


def test_create_income_and_numeric_amount(auth_client: TestClient):
    r = _post(auth_client, amount=100)
    assert r.status_code == 201
    assert r.json()["amount"] == "100.00"
    r = _post(auth_client, amount=12.5)
    assert r.status_code == 201
    assert r.json()["amount"] == "12.50"


def test_description_trimmed(auth_client: TestClient):
    r = _post(auth_client, description="  Kawa  ")
    assert r.status_code == 201
    assert r.json()["description"] == "Kawa"


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"},
        {"amount": "0.00"},
        {"amount": "1.005"},
        {"amount": "-1.005"},
        {"amount": "abc"},
        {"amount": "1000000000"},
        {"amount": "-1000000000"},
        {"description": ""},
        {"description": "   "},
        {"description": "x" * 501},
        {"date": "nie-data"},
        {"date": None},
    ],
)
def test_create_validation_422(auth_client: TestClient, overrides):
    assert _post(auth_client, **overrides).status_code == 422


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
    total = sum(Decimal(a) for a in amounts)
    assert total == Decimal("0.30")


def test_list_all_sorted_date_desc_then_id_desc(auth_client: TestClient):
    a = _post(auth_client, date="2026-03-01", description="a").json()["id"]
    b = _post(auth_client, date="2026-03-05", description="b").json()["id"]
    c = _post(auth_client, date="2026-03-05", description="c").json()["id"]
    d = _post(auth_client, date="2026-01-31", description="d").json()["id"]
    r = auth_client.get("/api/transactions")
    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == [c, b, a, d]


def test_list_month_filter_boundaries(auth_client: TestClient):
    _post(auth_client, date="2026-02-28", description="feb")
    first = _post(auth_client, date="2026-03-01", description="first").json()["id"]
    last = _post(auth_client, date="2026-03-31", description="last").json()["id"]
    _post(auth_client, date="2026-04-01", description="apr")
    r = auth_client.get("/api/transactions", params={"month": "2026-03"})
    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == [last, first]


def test_list_month_december(auth_client: TestClient):
    _post(auth_client, date="2026-12-31")
    _post(auth_client, date="2027-01-01")
    r = auth_client.get("/api/transactions", params={"month": "2026-12"})
    assert len(r.json()) == 1


def test_list_empty_month(auth_client: TestClient):
    r = auth_client.get("/api/transactions", params={"month": "2020-01"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "2026-3", "202603", "abc", "2026-03-01"])
def test_list_bad_month_422(auth_client: TestClient, month):
    assert auth_client.get("/api/transactions", params={"month": month}).status_code == 422


def test_list_isolation(auth_client: TestClient, other_auth_client: TestClient):
    mine = _post(auth_client, description="moja").json()["id"]
    theirs = _post(other_auth_client, description="cudza").json()["id"]
    assert [t["id"] for t in auth_client.get("/api/transactions").json()] == [mine]
    assert [t["id"] for t in other_auth_client.get("/api/transactions").json()] == [theirs]


def test_delete_ok(auth_client: TestClient):
    tid = _post(auth_client).json()["id"]
    r = auth_client.delete(f"/api/transactions/{tid}")
    assert r.status_code == 204
    assert auth_client.get("/api/transactions").json() == []
    assert auth_client.delete(f"/api/transactions/{tid}").status_code == 404


def test_delete_missing_404(auth_client: TestClient):
    r = auth_client.delete("/api/transactions/999999")
    assert r.status_code == 404
    assert r.json() == {"detail": "Nie znaleziono transakcji"}


def test_delete_other_users_transaction_404(auth_client: TestClient, other_auth_client: TestClient):
    tid = _post(other_auth_client).json()["id"]
    r = auth_client.delete(f"/api/transactions/{tid}")
    assert r.status_code == 404
    assert r.json() == {"detail": "Nie znaleziono transakcji"}
    assert len(other_auth_client.get("/api/transactions").json()) == 1


def test_date_type_sanity():
    assert date(2026, 3, 1) < date(2026, 4, 1)


@pytest.mark.parametrize("amount", [1e30, "1E+30", "-1e50"])
def test_huge_amount_is_422(auth_client, amount):
    body = {"date": "2026-01-01", "amount": amount, "description": "x"}
    assert auth_client.post("/api/transactions", json=body).status_code == 422


def test_out_of_range_month_filter_is_422(auth_client):
    assert auth_client.get("/api/transactions?month=9999-12").status_code == 422
