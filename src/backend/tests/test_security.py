"""Cross-cutting security: session required, user isolation, input bounds."""

import re

import pytest
from fastapi.testclient import TestClient

from coffer.main import app

PUBLIC = {"/api/health", "/api/auth/register", "/api/auth/login", "/api/auth/logout"}


def _fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda m: "2026-10" if "month" in m.group(0) else "1", path)


# app.routes holds lazy router includes, so read the finished route table from OpenAPI.
ROUTES = sorted(
    (method.upper(), _fill(path))
    for path, item in app.openapi()["paths"].items()
    if path not in PUBLIC
    for method in item
    if method in {"get", "post", "put", "patch", "delete"}
)


# --- Requirement: Access control, scenario "No session" ---


def test_route_table_is_not_empty() -> None:
    assert ("GET", "/api/auth/me") in ROUTES
    assert ("GET", "/api/transactions") in ROUTES
    assert len(ROUTES) >= 20


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_protected_route_requires_session(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path)
    assert response.status_code == 401, f"{method} {path}"
    assert response.json() == {"detail": "Wymagane logowanie"}


# --- Requirement: Access control, scenario "Another user's resource" ---

TX = {"date": "2026-10-01", "amount": "-5.00", "description": "x"}
HOLDING = {"name": "ETF", "asset_class": "etf", "quantity": "1", "purchase_price": "1.00"}
CSV = (
    "Data operacji;Data księgowania;Opis;Kwota;Waluta;Saldo po operacji\n"
    "01.10.2026;01.10.2026;KAWA;-5,00;PLN;0\n"
).encode()


def _draft(client: TestClient) -> str:
    r = client.post(
        "/api/imports", data={"bank": "testbank"}, files={"file": ("a.csv", CSV, "text/csv")}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _foreign_requests(owner: TestClient) -> list[tuple[str, str, dict | None]]:
    tx = owner.post("/api/transactions", json=TX).json()["id"]
    holding = owner.post("/api/portfolio/holdings", json=HOLDING).json()["id"]
    draft = _draft(owner)
    return [
        ("PATCH", f"/api/transactions/{tx}", {"description": "y"}),
        ("DELETE", f"/api/transactions/{tx}", None),
        ("PATCH", f"/api/portfolio/holdings/{holding}", {"name": "y"}),
        ("DELETE", f"/api/portfolio/holdings/{holding}", None),
        ("GET", f"/api/imports/{draft}", None),
        ("POST", f"/api/imports/{draft}/commit", {}),
        ("DELETE", f"/api/imports/{draft}", None),
    ]


def test_other_users_resources_are_404_and_untouched(
    auth_client: TestClient, other_auth_client: TestClient
) -> None:
    for method, path, body in _foreign_requests(auth_client):
        r = other_auth_client.request(method, path, json=body)
        assert r.status_code == 404, f"{method} {path}"
    # the owner still sees everything
    assert len(auth_client.get("/api/transactions").json()) == 1
    assert len(auth_client.get("/api/portfolio/holdings").json()) == 1
    assert other_auth_client.get("/api/transactions").json() == []
    assert other_auth_client.get("/api/portfolio/holdings").json() == []


@pytest.mark.parametrize("draft_id", ["%00", "x" * 100])
def test_malformed_draft_id_is_404(auth_client: TestClient, draft_id: str) -> None:
    assert auth_client.get(f"/api/imports/{draft_id}").status_code == 404
    assert auth_client.post(f"/api/imports/{draft_id}/commit", json={}).status_code == 404
    assert auth_client.delete(f"/api/imports/{draft_id}").status_code == 404


# --- Input bounds: 422, never 500 ---

HUGE = "1" * 30


@pytest.mark.parametrize(
    ("path", "base", "field"),
    [
        ("/api/transactions", TX, "description"),
        ("/api/portfolio/holdings", HOLDING, "name"),
        ("/api/portfolio/holdings", HOLDING, "symbol"),
        ("/api/portfolio/holdings", HOLDING, "note"),
    ],
)
def test_nul_byte_in_text_is_422(auth_client: TestClient, path: str, base: dict, field: str):
    r = auth_client.post(path, json=base | {field: "a\x00b"})
    assert r.status_code == 422
    assert auth_client.get(path).json() == []


@pytest.mark.parametrize(
    ("path", "base", "field", "value"),
    [
        ("/api/transactions", TX, "amount", HUGE),
        ("/api/transactions", TX, "amount", "NaN"),
        ("/api/transactions", TX, "description", "x" * 501),
        ("/api/portfolio/holdings", HOLDING, "name", "x" * 101),
        ("/api/portfolio/holdings", HOLDING, "quantity", HUGE),
        ("/api/portfolio/holdings", HOLDING, "purchase_price", HUGE),
    ],
)
def test_oversized_or_non_finite_values_are_422(
    auth_client: TestClient, path: str, base: dict, field: str, value: str
) -> None:
    assert auth_client.post(path, json=base | {field: value}).status_code == 422


def test_huge_budget_limit_is_422(auth_client: TestClient, category_id) -> None:
    r = auth_client.put(f"/api/budget/limits/{category_id('Jedzenie')}", json={"amount": HUGE})
    assert r.status_code == 422
