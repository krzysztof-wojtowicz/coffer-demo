"""Exploit regression: NUL bytes in text fields crashed the insert (500 instead of 422)."""


def test_nul_in_description_is_rejected(auth_client):
    r = auth_client.post(
        "/api/transactions", json={"date": "2026-10-01", "amount": "-5.00", "description": "a\x00b"}
    )
    assert r.status_code == 422
