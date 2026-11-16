"""Black-box contract tests for E5-03 (agent engine API). Written from E5-00/E5-03."""

import json
from decimal import Decimal

import pytest

from coffer.agent.api import get_llm_client
from coffer.agent.llm import LLMUnavailable
from coffer.agent.testing import FakeLLM
from coffer.core.config import get_settings
from coffer.main import app

RUN = "/api/agent/actions/portfolio_review/run"
SECRET_NAME = "SEKRETNA-NAZWA-XYZ"
SECRET_NOTE = "SEKRETNA-NOTATKA-QQQ"
STATUSES = {"ok", "unavailable", "limited", "timeout", "invalid", "no_data"}


@pytest.fixture
def use_llm():
    def _use(llm):
        app.dependency_overrides[get_llm_client] = lambda: llm
        return llm

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("coffer.agent.llm._sleep", lambda _s: None, raising=False)


def add_holdings(client):
    for name, cls, sym, val in [
        (SECRET_NAME, "real_estate", None, "60000.00"),
        ("Gotowka", "cash", None, "40000.00"),
    ]:
        r = client.post(
            "/api/portfolio/holdings",
            json={
                "name": name,
                "asset_class": cls,
                "symbol": sym,
                "quantity": "1",
                "purchase_price": val,
                "manual_value": val,
                "note": SECRET_NOTE,
            },
        )
        assert r.status_code == 201, r.text


def final(headline="Portfel wymaga uwagi"):
    return json.dumps(
        {
            "action": "final",
            "answer": {
                "headline": headline,
                "findings": [
                    {
                        "title": "Struktura",
                        "detail": "Portfel jest skoncentrowany w jednej klasie.",
                        "refers_to": "portfolio",
                        "value": None,
                    }
                ],
                "recommendations": [],
                "risks": ["Koncentracja"],
                "source_urls": [],
            },
        }
    )


def test_actions_and_tools_require_auth(client):
    for path in (
        "/api/agent/actions",
        "/api/agent/tools",
        "/api/agent/runs",
        "/api/agent/suggestions",
    ):
        assert client.get(path).status_code == 401
    assert client.post(RUN, json={"params": {}}).status_code == 401
    assert client.get("/api/agent/runs/1").status_code == 401


def test_actions_catalog(auth_client):
    r = auth_client.get("/api/agent/actions")
    assert r.status_code == 200
    items = {a["id"]: a for a in r.json()}
    assert "portfolio_review" in items
    a = items["portfolio_review"]
    for k in ("id", "name", "description", "params", "tools", "uses_user_data", "uses_internet"):
        assert k in a
    assert a["uses_user_data"] is True


def test_tools_catalog(auth_client):
    r = auth_client.get("/api/agent/tools")
    assert r.status_code == 200
    tools = {t["name"]: t for t in r.json()}
    for n in (
        "get_portfolio",
        "get_net_worth",
        "target_allocation",
        "get_month_analysis",
        "get_investment_profile",
    ):
        assert n in tools
    for t in tools.values():
        assert t["group"] in ("user_data", "market", "calc")
        assert isinstance(t["uses_internet"], bool) and "parameters" in t
    assert tools["target_allocation"]["group"] == "calc"
    assert tools["get_portfolio"]["group"] == "user_data"


def test_unknown_action_404(auth_client, use_llm):
    use_llm(FakeLLM([]))
    r = auth_client.post("/api/agent/actions/nope/run", json={"params": {}})
    assert r.status_code == 404
    assert r.json()["detail"] == "Nie znaleziono akcji"


def test_bad_params_422(auth_client, use_llm):
    use_llm(FakeLLM([]))
    r = auth_client.post(RUN, json={"params": "not-an-object"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "old", ["/api/agent/surplus", "/api/agent/surplus/stream", "/api/agent/investment/advice"]
)
def test_legacy_endpoints_removed(auth_client, old):
    assert auth_client.post(old, json={"month": "2025-03"}).status_code in (404, 405)
    assert auth_client.post(old, json={"month": "2025-03"}).status_code != 200


def test_empty_portfolio_no_data(auth_client, use_llm):
    llm = use_llm(FakeLLM([final()]))
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["ai_status"] == "no_data" and body["source"] == "none"
    assert llm.calls == []  # model never called
    assert body["suggestion_id"] is None  # D6: no_data not stored
    assert auth_client.get("/api/agent/suggestions").json()["total"] == 0


def test_no_llm_falls_back_to_rules(auth_client, use_llm):
    add_holdings(auth_client)
    use_llm(None)
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    b = r.json()
    assert b["ai_status"] == "unavailable" and b["source"] == "rules"
    rep = b["report"]
    assert rep["headline"] and rep["disclaimer"]
    assert any(f["kind"] in ("money", "percent", "number", "text", "date") for f in rep["facts"])
    assert b["suggestion_id"] is not None
    s = auth_client.get(f"/api/agent/suggestions/{b['suggestion_id']}").json()
    assert s["source"] == "rules" and s["ai_status"] == "unavailable"


def test_llm_unavailable_exception_falls_back(auth_client, use_llm):
    add_holdings(auth_client)
    use_llm(FakeLLM([LLMUnavailable("down")]))
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    assert r.json()["ai_status"] == "unavailable" and r.json()["source"] == "rules"


def test_ok_path_trace_shape_and_tokens(auth_client, use_llm, db):
    add_holdings(auth_client)
    llm = use_llm(FakeLLM([final()], provider="openai", input_tokens=120, output_tokens=30))
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    b = r.json()
    assert b["ai_status"] == "ok" and b["source"] == "ai", b
    assert b["provider"] == "openai" and b["model"] == "fake"
    assert b["run_id"] and b["suggestion_id"]
    assert len(llm.calls) == 1
    run = auth_client.get(f"/api/agent/runs/{b['run_id']}").json()
    assert run["status"] == "ok" and run["provider"] == "openai"
    assert run["input_tokens"] == 120 and run["output_tokens"] == 30
    assert run["llm_calls"] == 1
    assert run["cost_usd"] is None or isinstance(run["cost_usd"], str)
    steps = run["steps"]
    assert steps and [s["index"] for s in steps] == list(range(len(steps)))
    kinds = {s["kind"] for s in steps}
    assert "tool" in kinds and "llm" in kinds
    for s in steps:
        assert s["status"] in ("ok", "error")
        assert s["started_ms"] >= 0 and s["duration_ms"] >= 0
    llm_step = next(s for s in steps if s["kind"] == "llm")
    assert llm_step["provider"] == "openai" and llm_step["model"] == "fake"
    assert llm_step["input_tokens"] == 120 and llm_step["output_tokens"] == 30
    assert llm_step["attempt"] == 1
    tool_steps = [s for s in steps if s["kind"] == "tool"]
    assert {s["origin"] for s in tool_steps} == {"prepare"}
    names = {s["name"] for s in tool_steps}
    assert {"get_portfolio", "get_net_worth", "target_allocation"} <= names
    starts = [s["started_ms"] for s in steps]
    assert starts == sorted(starts)
    assert run["messages"] and run["params"] == {} and run["prompt_version"]
    # daily usage table has summed tokens
    from sqlalchemy import text

    row = db.execute(text("SELECT runs, input_tokens, output_tokens FROM llm_usage_daily")).one()
    assert tuple(row) == (1, 120, 30)


def test_ok_report_schema_amounts_are_strings(auth_client, use_llm):
    add_holdings(auth_client)
    use_llm(FakeLLM([final()]))
    rep = auth_client.post(RUN, json={"params": {}}).json()["report"]
    for k in (
        "headline",
        "facts",
        "tables",
        "findings",
        "recommendations",
        "risks",
        "sources",
        "disclaimer",
    ):
        assert k in rep
    assert all(isinstance(f["value"], str) for f in rep["facts"])
    for t in rep["tables"]:
        for row in t["rows"]:
            assert all(isinstance(v, str) for v in row.values())
    assert any(t["id"] == "allocation" for t in rep["tables"])


def test_daily_limit_gives_200_rules(auth_client, use_llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 1)
    add_holdings(auth_client)
    use_llm(FakeLLM([final(), final()]))
    first = auth_client.post(RUN, json={"params": {}})
    second = auth_client.post(RUN, json={"params": {}})
    assert first.json()["ai_status"] == "ok"
    assert second.status_code == 200
    assert second.json()["ai_status"] == "limited" and second.json()["source"] == "rules"


def test_invalid_answers_fall_back(auth_client, use_llm, no_sleep):
    add_holdings(auth_client)
    bad = final("Zysk wyniesie 777777.77 zl")  # number not present in tool data
    llm = use_llm(FakeLLM([bad, bad, bad, bad]))
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    b = r.json()
    assert b["ai_status"] == "invalid" and b["source"] == "rules"
    run = auth_client.get(f"/api/agent/runs/{b['run_id']}").json()
    assert run["status"] == "invalid" and run["validation_errors"]
    kinds = [s["kind"] for s in run["steps"]]
    assert "validation" in kinds and "fallback" in kinds
    assert len(llm.calls) <= get_settings().agent_max_attempts + 3


def test_tool_outside_action_tools_does_not_abort(auth_client, use_llm):
    add_holdings(auth_client)
    call = json.dumps({"action": "call_tool", "tool": "get_quotes", "args": {}})
    llm = use_llm(FakeLLM([call, final()]))
    r = auth_client.post(RUN, json={"params": {}})
    assert r.status_code == 200
    b = r.json()
    assert b["ai_status"] == "ok"
    run = auth_client.get(f"/api/agent/runs/{b['run_id']}").json()
    model_steps = [s for s in run["steps"] if s["kind"] == "tool" and s["origin"] == "model"]
    assert model_steps and model_steps[0]["status"] == "error" and model_steps[0]["error"]
    assert len(llm.calls) == 2  # model got a message back and continued


def test_privacy_no_email_or_descriptions_to_llm(auth_client, use_llm, user, add_tx, budget_cats):
    from datetime import date

    add_holdings(auth_client)
    add_tx(user, date(2025, 3, 5), "-10.00", budget_cats[0].id, "OPIS-TRANSAKCJI-ZZZ")
    llm = use_llm(FakeLLM([final()]))
    auth_client.post(RUN, json={"params": {}})
    assert llm.calls
    blob = json.dumps(
        [{"system": c["system"], "messages": [str(m) for m in c["messages"]]} for c in llm.calls],
        default=str,
    )
    for secret in (user.email, SECRET_NAME, SECRET_NOTE, "OPIS-TRANSAKCJI-ZZZ"):
        assert secret not in blob
    # trace messages stored for the run must be clean too
    runs = auth_client.get("/api/agent/runs").json()["items"]
    run = auth_client.get(f"/api/agent/runs/{runs[0]['id']}").json()
    stored = json.dumps(run["messages"], default=str)
    for secret in (user.email, SECRET_NAME, SECRET_NOTE):
        assert secret not in stored


def test_runs_and_suggestions_isolation_and_filters(auth_client, other_auth_client, use_llm):
    add_holdings(auth_client)
    use_llm(None)
    ids = [auth_client.post(RUN, json={"params": {}}).json() for _ in range(3)]
    runs = auth_client.get("/api/agent/runs?limit=2&offset=0").json()
    assert runs["total"] == 3 and len(runs["items"]) == 2
    item = runs["items"][0]
    for k in (
        "id",
        "action",
        "status",
        "provider",
        "model",
        "llm_calls",
        "tool_calls_count",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "duration_ms",
        "created_at",
        "suggestion_id",
    ):
        assert k in item
    asc = auth_client.get("/api/agent/runs?order=asc").json()["items"]
    assert [i["id"] for i in asc] == sorted(i["id"] for i in asc)
    assert auth_client.get("/api/agent/runs?status=ok").json()["total"] == 0
    assert auth_client.get("/api/agent/runs?status=unavailable").json()["total"] == 3
    for bad in ("limit=0", "limit=101", "sort=bogus", "order=sideways"):
        assert auth_client.get(f"/api/agent/runs?{bad}").status_code == 422
    for bad in ("limit=0", "limit=51", "source=nope"):
        assert auth_client.get(f"/api/agent/suggestions?{bad}").status_code == 422
    sug = auth_client.get("/api/agent/suggestions?source=rules&limit=2").json()
    assert sug["total"] == 3 and len(sug["items"]) == 2
    assert auth_client.get("/api/agent/suggestions?source=ai").json()["total"] == 0
    # other user sees nothing and cannot read foreign resources
    assert other_auth_client.get("/api/agent/runs").json() == {"items": [], "total": 0}
    assert other_auth_client.get("/api/agent/suggestions").json()["total"] == 0
    r = other_auth_client.get(f"/api/agent/runs/{ids[0]['run_id']}")
    assert r.status_code == 404 and r.json()["detail"] == "Nie znaleziono przebiegu agenta"
    s = other_auth_client.get(f"/api/agent/suggestions/{ids[0]['suggestion_id']}")
    assert s.status_code == 404 and s.json()["detail"] == "Nie znaleziono sugestii"
    assert auth_client.get("/api/agent/runs/999999").status_code == 404


def test_sse_run(auth_client, use_llm):
    add_holdings(auth_client)
    use_llm(FakeLLM([final()]))
    r = auth_client.post(RUN, json={"params": {}}, headers={"Accept": "text/event-stream"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [ln[len("event:") :].strip() for ln in r.text.splitlines() if ln.startswith("event:")]
    assert "step" in events and events[-1] == "result"
    data = [ln for ln in r.text.splitlines() if ln.startswith("data:")][-1][5:]
    assert json.loads(data)["ai_status"] == "ok"


def test_reserve_run_atomic_limit(db):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from coffer.accounts.models import User
    from coffer.agent.service import reserve_run
    from tests.conftest import TEST_URL

    u = User(email="rr@example.com", password_hash="x")
    db.add(u)
    db.commit()
    engine = create_engine(TEST_URL)
    now = datetime.now(UTC)

    def go(_):
        with Session(engine) as s:
            ok = reserve_run(s, u.id, now, 1)
            s.commit()
            return ok

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(go, range(8)))
    engine.dispose()
    assert results.count(True) == 1


def test_money_fact_values_decimal_parsable(auth_client, use_llm):
    add_holdings(auth_client)
    use_llm(None)
    rep = auth_client.post(RUN, json={"params": {}}).json()["report"]
    for f in rep["facts"]:
        if f["kind"] in ("money", "percent", "number"):
            Decimal(
                f["value"].replace(" ", "").replace("%", "").replace("zł", "").replace(",", ".")
            )
