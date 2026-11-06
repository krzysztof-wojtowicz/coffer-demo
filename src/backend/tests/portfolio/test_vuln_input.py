"""Exploit regressions: NUL bytes in holding text and huge-but-valid amounts in the summary."""

import pytest

from coffer.portfolio import service

BASE = "/api/portfolio/holdings"
HUGE = {
    "name": "Max",
    "asset_class": "cash",
    "quantity": "999999999999.99999999",
    "purchase_price": "999999999999.99",
}


@pytest.mark.parametrize("field", ["name", "symbol", "note"])
def test_nul_in_holding_text_is_rejected(auth_client, field):
    body = {"name": "Apple", "asset_class": "stock", "quantity": "1", "purchase_price": "1.00"}
    body[field] = "a\x00b"
    assert auth_client.post(BASE, json=body).status_code == 422
    assert auth_client.get(BASE).json() == []


def test_summary_survives_max_amounts(auth_client, monkeypatch):
    monkeypatch.setattr(service, "fetch_prices", lambda symbols: None)
    for _ in range(1000):  # 1000 x ~1e24 needs 30 digits > default Decimal precision (28)
        assert auth_client.post(BASE, json=HUGE).status_code == 201
    r = auth_client.get("/api/portfolio/summary")
    assert r.status_code == 200
    assert r.json()["total_cost"].startswith("99999999999")
