import json

import pytest
from sqlalchemy import select

from coffer.agent.llm import LLMUnavailable
from coffer.agent.models import AgentRun, Suggestion
from coffer.agent.testing import FakeLLM

from .conftest import final

RUN = "/api/agent/actions/portfolio_review/run"
SSE = {"accept": "text/event-stream"}


def parse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if name:
            events.append((name, data))
    return events


def test_endpoints_require_auth(client):
    assert client.get("/api/agent/actions").status_code == 401
    assert client.get("/api/agent/tools").status_code == 401
    assert client.post(RUN, json={"params": {}}).status_code == 401


def test_list_actions(auth_client):
    items = auth_client.get("/api/agent/actions").json()
    review = next(a for a in items if a["id"] == "portfolio_review")
    assert review["name"] == "Analiza portfela" and review["params"] == []
    assert review["uses_user_data"] is True and review["uses_internet"] is True
    assert "get_portfolio" in review["tools"]


def test_list_tools(auth_client):
    items = auth_client.get("/api/agent/tools").json()
    by_name = {t["name"]: t for t in items}
    assert by_name["target_allocation"]["group"] == "calc"
    assert by_name["get_net_worth"]["group"] == "user_data"
    assert set(by_name["target_allocation"]) == {
        "name",
        "description",
        "group",
        "uses_internet",
        "parameters",
    }


def test_unknown_action_404(auth_client):
    r = auth_client.post("/api/agent/actions/nope/run", json={"params": {}})
    assert r.status_code == 404 and r.json()["detail"] == "Nie znaleziono akcji"


def test_legacy_endpoints_are_gone(auth_client):
    assert auth_client.post("/api/agent/surplus", json={"month": "2025-03"}).status_code == 404
    assert auth_client.post("/api/agent/investment/advice", json={}).status_code == 404


def test_bad_params_422(auth_client, profile):
    r = auth_client.post(RUN, json={"params": {"month": "2025-03"}})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][:2] == ["body", "params"]
    assert auth_client.post(RUN, json={"params": "x"}).status_code == 422


def test_run_json_ok(auth_client, profile, use_llm, db):
    use_llm(FakeLLM([final()], provider="ollama", input_tokens=10, output_tokens=5))
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "portfolio_review" and body["ai_status"] == "ok"
    assert body["source"] == "ai" and body["provider"] == "ollama" and body["model"] == "fake"
    assert body["report"]["tables"][0]["id"] == "allocation"
    assert isinstance(body["duration_ms"], int)
    assert db.scalars(select(AgentRun)).one().id == body["run_id"]
    assert db.scalars(select(Suggestion)).one().id == body["suggestion_id"]


def test_run_without_llm_is_200_with_rules(auth_client, profile, use_llm):
    use_llm(None)
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    assert r.json()["ai_status"] == "unavailable" and r.json()["source"] == "rules"


def test_run_empty_portfolio_no_data(auth_client, use_llm):
    use_llm(FakeLLM([]))
    body = auth_client.post(RUN, json={"params": {}}).json()
    assert body["ai_status"] == "no_data" and body["run_id"] and body["suggestion_id"] is None


def test_run_limit_is_200_not_429(auth_client, profile, use_llm, monkeypatch):
    from coffer.core.config import Settings

    monkeypatch.setattr(
        "coffer.agent.runner.get_settings",
        lambda: Settings.model_construct(
            agent_daily_limit=0, agent_max_attempts=2, agent_timeout_s=60
        ),
    )
    use_llm(FakeLLM([final()]))
    body = auth_client.post(RUN, json={"params": {}}).json()
    assert body["ai_status"] == "limited" and body["source"] == "rules"


def test_unexpected_error_is_500(auth_client, profile, use_llm):
    use_llm(FakeLLM([]))  # exhausted script -> IndexError inside the loop
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 500 and r.json()["detail"] == "Nie udało się wykonać akcji"


def test_sse_events(auth_client, profile, use_llm):
    use_llm(FakeLLM([final()]))
    r = auth_client.post(RUN, json={"params": {}}, headers=SSE)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["x-accel-buffering"] == "no"
    assert r.text.startswith(": ping\n\n")
    events = parse(r.text)
    names = [n for n, _ in events]
    assert names[0] == "status" and names[-1] == "result" and names.count("result") == 1
    steps = [d for n, d in events if n == "step"]
    assert steps and set(steps[0]) == {"index", "kind", "name", "status", "duration_ms"}
    assert [s["index"] for s in steps] == list(range(len(steps)))
    result = events[-1][1]
    assert result["ai_status"] == "ok" and result["report"]["headline"]


def test_sse_fallback_still_result(auth_client, profile, use_llm):
    use_llm(FakeLLM([LLMUnavailable("503")]))
    events = parse(auth_client.post(RUN, json={"params": {}}, headers=SSE).text)
    assert events[-1][0] == "result" and events[-1][1]["ai_status"] == "unavailable"


def test_sse_unexpected_error_event(auth_client, profile, use_llm):
    use_llm(FakeLLM([]))
    events = parse(auth_client.post(RUN, json={"params": {}}, headers=SSE).text)
    assert events[-1] == ("error", {"detail": "Nie udało się wykonać akcji"})
    assert "result" not in [n for n, _ in events]


def test_sse_bad_params_is_plain_422(auth_client):
    r = auth_client.post(RUN, json={"params": {"x": 1}}, headers=SSE)
    assert r.status_code == 422


@pytest.mark.parametrize("path", ["/api/agent/runs", "/api/agent/suggestions"])
def test_history_requires_auth(client, path):
    assert client.get(path).status_code == 401
