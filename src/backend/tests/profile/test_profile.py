import pytest

from coffer.analytics.allocation import ASSET_CLASSES
from coffer.profile.models import HORIZONS, RISK_LEVELS

VALID = {"horizon": "long", "risk": "medium", "preferred_classes": ["etf", "bond"]}


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
    assert body["preferred_classes"] == ["etf", "bond"]
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
    assert got["preferred_classes"] == ["etf", "bond"]


def test_user_isolation(auth_client, other_auth_client):
    auth_client.put("/api/profile", json=VALID)
    assert other_auth_client.get("/api/profile").json() is None
    other = {"horizon": "short", "risk": "low", "preferred_classes": ["cash"]}
    other_auth_client.put("/api/profile", json=other)
    assert auth_client.get("/api/profile").json()["horizon"] == "long"
    assert other_auth_client.get("/api/profile").json()["horizon"] == "short"


def test_get_returns_target_summing_to_100(auth_client):
    auth_client.put(
        "/api/profile",
        json={"horizon": "medium", "risk": "medium", "preferred_classes": list(ASSET_CLASSES)},
    )
    body = auth_client.get("/api/profile").json()
    assert {t["asset_class"]: t["share_pct"] for t in body["target"]} == {
        "stock": 11,
        "etf": 34,
        "bond": 40,
        "cash": 10,
        "commodity": 5,
    }


def test_put_response_has_target_and_redistributes(auth_client):
    r = auth_client.put(
        "/api/profile",
        json={
            "horizon": "medium",
            "risk": "medium",
            "preferred_classes": [c for c in ASSET_CLASSES if c != "stock"],
        },
    )
    assert r.status_code == 200
    got = {t["asset_class"]: t["share_pct"] for t in r.json()["target"]}
    assert got == {"etf": 45, "bond": 40, "cash": 10, "commodity": 5}


@pytest.mark.parametrize("old", ["stocks", "deposit", "bonds"])
def test_old_class_codes_422_and_profile_kept(auth_client, old):
    auth_client.put("/api/profile", json=VALID)
    r = auth_client.put("/api/profile", json={**VALID, "preferred_classes": [old]})
    assert r.status_code == 422
    assert auth_client.get("/api/profile").json()["preferred_classes"] == ["etf", "bond"]


def test_target_is_per_user(auth_client, other_auth_client):
    auth_client.put("/api/profile", json=VALID)
    other_auth_client.put(
        "/api/profile", json={"horizon": "short", "risk": "low", "preferred_classes": ["cash"]}
    )
    assert (
        auth_client.get("/api/profile").json()["target"]
        != other_auth_client.get("/api/profile").json()["target"]
    )
    assert other_auth_client.get("/api/profile").json()["target"] == [
        {"asset_class": "cash", "share_pct": 100}
    ]
