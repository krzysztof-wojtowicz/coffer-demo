import pytest

from tests.budget.test_budget_api import add_tx  # noqa: F401


def test_requires_auth(client):
    assert client.get("/api/budget/limits").status_code == 401
    assert client.get("/api/budget/2026-03/insights").status_code == 401


def test_put_get_delete(auth_client, category_id):
    food = category_id("Jedzenie")
    r = auth_client.put(f"/api/budget/limits/{food}", json={"amount": "500.00"})
    assert r.status_code == 200
    assert r.json() == {"category_id": food, "category_name": "Jedzenie", "amount": "500.00"}
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "600"})
    assert auth_client.get("/api/budget/limits").json()[0]["amount"] == "600.00"
    assert auth_client.delete(f"/api/budget/limits/{food}").status_code == 204
    assert auth_client.get("/api/budget/limits").json() == []
    r = auth_client.delete(f"/api/budget/limits/{food}")
    assert (r.status_code, r.json()["detail"]) == (404, "Nie ustawiono limitu dla tej kategorii")


def test_put_errors(auth_client, category_id):
    r = auth_client.put("/api/budget/limits/999999", json={"amount": "5.00"})
    assert (r.status_code, r.json()["detail"]) == (404, "Nie znaleziono kategorii")
    r = auth_client.put(f"/api/budget/limits/{category_id('Inwestycje')}", json={"amount": "5"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Limit można ustawić tylko dla kategorii budżetowej"
    food = category_id("Jedzenie")
    for bad in ["0", "-1", "1.234", "1000000000000.00", "abc"]:
        r = auth_client.put(f"/api/budget/limits/{food}", json={"amount": bad})
        assert r.status_code == 422


def test_user_isolation(auth_client, other_auth_client, category_id):
    food = category_id("Jedzenie")
    auth_client.put(f"/api/budget/limits/{food}", json={"amount": "500.00"})
    assert other_auth_client.get("/api/budget/limits").json() == []
    assert other_auth_client.delete(f"/api/budget/limits/{food}").status_code == 404
    assert len(auth_client.get("/api/budget/limits").json()) == 1


def test_insights_empty(auth_client):
    body = auth_client.get("/api/budget/2026-01/insights").json()
    assert body == {
        "month": "2026-01",
        "previous_month": "2025-12",
        "comparison": [],
        "top_growth": [],
        "limits": [],
    }


@pytest.mark.parametrize("path", ["2026-13", "abc"])
def test_insights_bad_month(auth_client, path):
    assert auth_client.get(f"/api/budget/{path}/insights").status_code == 422
