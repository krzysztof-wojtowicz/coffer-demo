import json

import pytest

from coffer.agent.llm import LLMUnavailable
from coffer.agent.testing import FakeLLM

from .conftest import DESCRIPTION, MONTH
from .test_surplus import BAD_NUMBER, GOOD, use_llm  # noqa: F401

URL = "/api/agent/surplus"


def test_requires_auth(client):
    assert client.get("/api/agent/runs").status_code == 401
    assert client.get("/api/agent/runs/1").status_code == 401


def test_list_and_detail(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    body = auth_client.post(URL, json={"month": MONTH}).json()
    items = auth_client.get("/api/agent/runs").json()
    assert len(items) == 1
    item = items[0]
    assert item["id"] == body["run_id"]
    assert item["task"] == "surplus" and item["status"] == "ok"
    assert item["model"] == "fake" and item["attempts"] == 1
    assert "created_at" in item and "duration_ms" in item
    assert "messages" not in item

    d = auth_client.get(f"/api/agent/runs/{body['run_id']}").json()
    assert d["prompt_version"] == "surplus_v2"
    assert [c["name"] for c in d["tool_calls"]][0] == "get_month_analysis"
    assert d["messages"][0]["role"] == "system"
    assert d["raw_outputs"] == [GOOD]
    assert d["validation_errors"] == []
    assert d["error"] is None
    assert {"input_tokens", "output_tokens"} <= d.keys()


def test_list_newest_first_and_limit(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD] * 3))
    ids = [auth_client.post(URL, json={"month": MONTH}).json()["run_id"] for _ in range(3)]
    items = auth_client.get("/api/agent/runs").json()
    assert [i["id"] for i in items] == ids[::-1]
    assert len(auth_client.get("/api/agent/runs?limit=2").json()) == 2


@pytest.mark.parametrize("limit", [0, 101])
def test_limit_validation(auth_client, limit):
    assert auth_client.get(f"/api/agent/runs?limit={limit}").status_code == 422


def test_invalid_run_visible(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([BAD_NUMBER, BAD_NUMBER]))
    body = auth_client.post(URL, json={"month": MONTH}).json()
    assert body["ai_status"] == "unavailable"
    d = auth_client.get(f"/api/agent/runs/{body['run_id']}").json()
    assert d["status"] == "invalid" and d["attempts"] == 2
    assert d["validation_errors"] and len(d["raw_outputs"]) == 2


def test_unavailable_run_visible(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([LLMUnavailable("x")]))
    auth_client.post(URL, json={"month": MONTH})
    assert auth_client.get("/api/agent/runs").json()[0]["status"] == "unavailable"


def test_no_surplus_run_visible(auth_client, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    auth_client.post(URL, json={"month": MONTH})
    assert auth_client.get("/api/agent/runs").json()[0]["status"] == "no_surplus"


def test_n03_run_has_no_personal_data(auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    rid = auth_client.post(URL, json={"month": MONTH}).json()["run_id"]
    d = auth_client.get(f"/api/agent/runs/{rid}").json()
    blob = json.dumps(d, ensure_ascii=False)
    assert "user@example.com" not in blob
    assert DESCRIPTION not in blob and "Kowalski" not in blob and "Wyplata firma" not in blob


def test_not_found(auth_client):
    r = auth_client.get("/api/agent/runs/9999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Nie znaleziono przebiegu agenta"


def test_isolation(auth_client, other_auth_client, surplus_data, use_llm):  # noqa: F811
    use_llm(FakeLLM([GOOD]))
    rid = auth_client.post(URL, json={"month": MONTH}).json()["run_id"]
    assert other_auth_client.get(f"/api/agent/runs/{rid}").status_code == 404
    assert other_auth_client.get("/api/agent/runs").json() == []
