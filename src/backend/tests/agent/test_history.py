import pytest

from coffer.agent.testing import FakeLLM

from .conftest import MONTH
from .test_surplus import GOOD, use_llm  # noqa: F401


def make(client, use_llm, n=1):  # noqa: F811
    use_llm(FakeLLM([GOOD] * n))
    return [client.post("/api/agent/surplus", json={"month": MONTH}).json() for _ in range(n)]


def test_requires_auth(client):
    assert client.get("/api/agent/suggestions").status_code == 401
    assert client.get("/api/agent/suggestions/1").status_code == 401


def test_empty(auth_client):
    r = auth_client.get("/api/agent/suggestions")
    assert r.status_code == 200 and r.json() == []


def test_saved_and_listed_newest_first(auth_client, surplus_data, use_llm):  # noqa: F811
    a, b = make(auth_client, use_llm, 2)
    items = auth_client.get("/api/agent/suggestions").json()
    assert [i["id"] for i in items] == [b["suggestion"]["id"], a["suggestion"]["id"]]
    assert items[0]["summary"] == a["suggestion"]["summary"]
    assert items[0]["month"] == MONTH and items[0]["type"] == "surplus"


def test_limit(auth_client, surplus_data, use_llm):  # noqa: F811
    make(auth_client, use_llm, 3)
    assert len(auth_client.get("/api/agent/suggestions?limit=2").json()) == 2


@pytest.mark.parametrize("limit", [0, 101, -1, "x"])
def test_limit_validation(auth_client, limit):
    assert auth_client.get(f"/api/agent/suggestions?limit={limit}").status_code == 422


def test_detail(auth_client, surplus_data, use_llm):  # noqa: F811
    (a,) = make(auth_client, use_llm)
    r = auth_client.get(f"/api/agent/suggestions/{a['suggestion']['id']}")
    assert r.status_code == 200
    assert r.json() == a["suggestion"]


def test_detail_not_found(auth_client):
    r = auth_client.get("/api/agent/suggestions/9999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Nie znaleziono sugestii"


def test_isolation(auth_client, other_auth_client, surplus_data, use_llm):  # noqa: F811
    (a,) = make(auth_client, use_llm)
    sid = a["suggestion"]["id"]
    assert other_auth_client.get(f"/api/agent/suggestions/{sid}").status_code == 404
    assert other_auth_client.get("/api/agent/suggestions").json() == []
    assert auth_client.get(f"/api/agent/suggestions/{sid}").status_code == 200
