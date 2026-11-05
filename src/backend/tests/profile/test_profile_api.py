import pytest
from fastapi.testclient import TestClient

from coffer.profile import service
from coffer.profile.models import ASSET_CLASSES, HORIZONS, RISK_LEVELS
from coffer.profile.schemas import ProfileIn

VALID = {"horizon": "long", "risk": "medium", "preferred_classes": ["etf", "bonds"]}


def test_get_without_profile_returns_null(auth_client):
    r = auth_client.get("/api/profile")
    assert r.status_code == 200
    assert r.json() is None


def test_put_then_get(auth_client):
    r = auth_client.put("/api/profile", json=VALID)
    assert r.status_code == 200
    body = r.json()
    assert body["horizon"] == "long"
    assert body["risk"] == "medium"
    assert body["preferred_classes"] == ["etf", "bonds"]
    assert body["updated_at"]
    got = auth_client.get("/api/profile").json()
    assert got == body


def test_put_overwrites(auth_client):
    auth_client.put("/api/profile", json=VALID)
    new = {"horizon": "short", "risk": "high", "preferred_classes": ["crypto"]}
    r = auth_client.put("/api/profile", json=new)
    assert r.status_code == 200
    got = auth_client.get("/api/profile").json()
    assert got["horizon"] == "short"
    assert got["risk"] == "high"
    assert got["preferred_classes"] == ["crypto"]


def test_all_enum_values_accepted(auth_client):
    for h in HORIZONS:
        for risk in RISK_LEVELS:
            r = auth_client.put(
                "/api/profile",
                json={"horizon": h, "risk": risk, "preferred_classes": list(ASSET_CLASSES)},
            )
            assert r.status_code == 200


@pytest.mark.parametrize(
    "patch",
    [
        {"horizon": "forever"},
        {"risk": "extreme"},
        {"preferred_classes": ["gold"]},
        {"preferred_classes": []},
        {"horizon": None},
        {"risk": None},
        {"preferred_classes": None},
    ],
)
def test_invalid_values_422(auth_client, patch):
    r = auth_client.put("/api/profile", json={**VALID, **patch})
    assert r.status_code == 422


@pytest.mark.parametrize("missing", ["horizon", "risk", "preferred_classes"])
def test_missing_field_422(auth_client, missing):
    body = {k: v for k, v in VALID.items() if k != missing}
    assert auth_client.put("/api/profile", json=body).status_code == 422


def test_duplicates_422_with_message(auth_client):
    r = auth_client.put("/api/profile", json={**VALID, "preferred_classes": ["etf", "etf"]})
    assert r.status_code == 422
    assert "Klasy aktywów nie mogą się powtarzać" in r.text


def test_invalid_put_does_not_change_profile(auth_client):
    auth_client.put("/api/profile", json=VALID)
    auth_client.put("/api/profile", json={**VALID, "preferred_classes": []})
    got = auth_client.get("/api/profile").json()
    assert got["preferred_classes"] == ["etf", "bonds"]


def test_user_isolation(auth_client, other_auth_client):
    auth_client.put("/api/profile", json=VALID)
    assert other_auth_client.get("/api/profile").json() is None
    other = {"horizon": "short", "risk": "low", "preferred_classes": ["cash"]}
    other_auth_client.put("/api/profile", json=other)
    assert auth_client.get("/api/profile").json()["horizon"] == "long"
    assert other_auth_client.get("/api/profile").json()["horizon"] == "short"


def test_requires_auth(client: TestClient):
    assert client.get("/api/profile").status_code == 401
    assert client.put("/api/profile", json=VALID).status_code == 401


def test_service_get_upsert(db, user):
    assert service.get(db, user.id) is None
    p = service.upsert(db, user.id, ProfileIn(**VALID))
    assert p.user_id == user.id
    assert p.preferred_classes == ["etf", "bonds"]
    p2 = service.upsert(
        db, user.id, ProfileIn(horizon="short", risk="low", preferred_classes=["cash"])
    )
    assert p2.horizon == "short"
    got = service.get(db, user.id)
    assert got is not None and got.risk == "low"
