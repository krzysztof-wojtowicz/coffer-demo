from coffer.agent.testing import FakeLLM
from tests.e5.conftest import final_answer, run_action_api


def _ok_run(client, use_llm, model="gpt-4o-mini", provider="openai", i=100, o=50):
    use_llm(
        FakeLLM(
            [final_answer("portfolio_review")],
            provider=provider,
            model=model,
            input_tokens=i,
            output_tokens=o,
        )
    )
    b = run_action_api(client, "portfolio_review").json()
    assert b["ai_status"] == "ok", b
    return b


def test_trace_of_ok_run(anna_client, use_llm):
    b = _ok_run(anna_client, use_llm)
    run = anna_client.get(f"/api/agent/runs/{b['run_id']}").json()
    steps = run["steps"]
    assert steps
    assert [s["index"] for s in steps] == list(range(len(steps)))
    starts = [s["started_ms"] for s in steps]
    assert starts == sorted(starts)
    assert all(s["duration_ms"] >= 0 and s["status"] in ("ok", "error") for s in steps)
    llm_steps = [s for s in steps if s["kind"] == "llm"]
    assert len(llm_steps) == 1
    s = llm_steps[0]
    assert s["provider"] == "openai" and s["model"] == "gpt-4o-mini"
    assert s["input_tokens"] == 100 and s["output_tokens"] == 50
    assert s["cost_usd"] is not None and float(s["cost_usd"]) > 0
    assert sum(x["duration_ms"] for x in steps) <= b["duration_ms"] + 2
    assert run["input_tokens"] == 100 and run["output_tokens"] == 50
    assert run["cost_usd"] is not None and run["provider"] == "openai"


def test_runs_sort_and_filters_consistent(anna_client, use_llm):
    _ok_run(anna_client, use_llm, i=1000, o=1000)
    _ok_run(anna_client, use_llm, i=10, o=10)
    _ok_run(anna_client, use_llm, i=500, o=500)
    r = anna_client.get("/api/agent/runs?sort=cost_usd&order=desc&provider=openai").json()
    assert r["total"] == 3
    costs = [float(i["cost_usd"]) for i in r["items"]]
    assert costs == sorted(costs, reverse=True)
    asc = anna_client.get("/api/agent/runs?sort=cost_usd&order=asc&provider=openai").json()
    assert [i["id"] for i in asc["items"]] == [i["id"] for i in reversed(r["items"])]
    tok = anna_client.get("/api/agent/runs?sort=tokens&order=desc").json()["items"]
    sums = [(i["input_tokens"] or 0) + (i["output_tokens"] or 0) for i in tok]
    assert sums == sorted(sums, reverse=True)
    page = anna_client.get("/api/agent/runs?limit=2&offset=2&sort=created_at&order=asc").json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert anna_client.get("/api/agent/runs?status=ok").json()["total"] == 3
    assert anna_client.get("/api/agent/runs?status=invalid").json()["total"] == 0
    assert anna_client.get("/api/agent/runs?action=budget_plan").json()["total"] == 0
    assert anna_client.get("/api/agent/runs?provider=gemini").json()["total"] == 0


def test_cost_is_decimal_string(anna_client, use_llm):
    from decimal import Decimal

    b = _ok_run(anna_client, use_llm)
    item = anna_client.get("/api/agent/runs").json()["items"][0]
    assert isinstance(item["cost_usd"], str)
    Decimal(item["cost_usd"])
    assert item["id"] == b["run_id"]


def test_unknown_model_cost_null(anna_client, use_llm):
    _ok_run(anna_client, use_llm, model="no-such-model-zz")
    assert anna_client.get("/api/agent/runs").json()["items"][0]["cost_usd"] is None


def test_ollama_cost_zero(anna_client, use_llm):
    from decimal import Decimal

    _ok_run(anna_client, use_llm, provider="ollama", model="llama3")
    item = anna_client.get("/api/agent/runs").json()["items"][0]
    assert Decimal(item["cost_usd"]) == 0
