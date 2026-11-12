from fastapi.testclient import TestClient


def _post(client: TestClient, **kw):
    body = {"date": "2026-03-10", "amount": "-45.50", "description": "Zakupy"}
    body.update(kw)
    return client.post("/api/transactions", json=body).json()


def test_requires_login(client: TestClient):
    assert client.patch("/api/transactions/1", json={}).status_code == 401


def test_update_all_fields(auth_client: TestClient, category_id):
    tid = _post(auth_client)["id"]
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
    assert body["currency"] == "PLN"


def test_partial_and_null_category_means_no_change(auth_client: TestClient, category_id):
    cid = category_id("Inne")
    created = _post(auth_client, category_id=cid)
    r = auth_client.patch(
        f"/api/transactions/{created['id']}", json={"description": "X", "category_id": None}
    )
    assert r.status_code == 200
    assert r.json() == {**created, "description": "X"}


def test_source_and_currency_ignored(auth_client: TestClient):
    tid = _post(auth_client)["id"]
    r = auth_client.patch(f"/api/transactions/{tid}", json={"source": "csv", "currency": "USD"})
    assert r.json()["source"] == "manual"
    assert r.json()["currency"] == "PLN"


def test_unknown_category_422(auth_client: TestClient):
    tid = _post(auth_client)["id"]
    r = auth_client.patch(f"/api/transactions/{tid}", json={"category_id": 999999})
    assert r.status_code == 422
    assert r.json()["detail"] == "Nieznana kategoria"


def test_validation_like_create(auth_client: TestClient):
    tid = _post(auth_client)["id"]
    for body in ({"amount": "0"}, {"amount": "1.234"}, {"description": "  "}, {"date": "x"}):
        assert auth_client.patch(f"/api/transactions/{tid}", json=body).status_code == 422


def test_missing_and_foreign_404(auth_client: TestClient, other_auth_client: TestClient):
    foreign = _post(other_auth_client)["id"]
    for tid in (foreign, 999999):
        r = auth_client.patch(f"/api/transactions/{tid}", json={"description": "x"})
        assert r.status_code == 404
        assert r.json()["detail"] == "Nie znaleziono transakcji"
    listed = other_auth_client.get("/api/transactions").json()
    assert listed[0]["description"] == "Zakupy"
