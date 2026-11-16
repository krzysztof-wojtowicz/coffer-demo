import json

import pytest

from tests.e5.conftest import (
    ACTION_CASES,
    EMAIL,
    SECRET_HOLDING,
    SECRET_NOTE,
    SECRET_TX,
    final_answer,
    run_action_api,
)

ID_KEYS = ('"user_id"', '"id":', '"holding_id"', '"transaction_id"', '"account_id"')


def _blob(obj) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)


@pytest.mark.parametrize(("action", "params"), ACTION_CASES, ids=[a for a, _ in ACTION_CASES])
def test_nothing_private_reaches_model_or_trace(anna_client, anna, use_llm, action, params):
    from tests.e5.conftest import final_answer as fa

    llm = use_llm(
        __import__("coffer.agent.testing", fromlist=["FakeLLM"]).FakeLLM(
            [fa(action)] * 3, provider="openai", input_tokens=10, output_tokens=5
        )
    )
    r = run_action_api(anna_client, action, params)
    assert r.status_code == 200, r.text
    assert r.json()["ai_status"] in ("ok", "invalid"), r.json()["ai_status"]
    assert llm.calls, "model must have been called"
    sent = _blob(
        [{"system": c["system"], "messages": [str(m) for m in c["messages"]]} for c in llm.calls]
    )
    run_id = r.json()["run_id"]
    stored = ""
    if run_id:
        run = anna_client.get(f"/api/agent/runs/{run_id}").json()
        stored = _blob({"messages": run["messages"], "steps": run["steps"]})
    for text in (sent, stored):
        for secret in (
            EMAIL,
            "anna.kowalska",
            SECRET_TX,
            SECRET_HOLDING,
            SECRET_NOTE,
            "Apple tajny",
        ):
            assert secret not in text, f"{secret!r} leaked in {action}"
        for key in ID_KEYS:
            assert key not in text, f"{key} leaked in {action}"
        assert f'"user_id": {anna.id}' not in text


def test_ok_runs_actually_called_the_model(anna_client, use_llm):
    """Guard against vacuous privacy tests: at least portfolio_review reaches the model."""
    from coffer.agent.testing import FakeLLM

    llm = use_llm(FakeLLM([final_answer("portfolio_review")]))
    r = run_action_api(anna_client, "portfolio_review")
    assert r.json()["ai_status"] == "ok" and len(llm.calls) == 1


def test_company_research_has_no_user_amounts(anna_client, use_llm):
    from coffer.agent.testing import FakeLLM

    llm = use_llm(FakeLLM([final_answer("company_research")] * 2))
    r = run_action_api(anna_client, "company_research", {"query": "PKO BP"})
    assert r.status_code == 200
    sent = _blob([{"s": c["system"], "m": [str(m) for m in c["messages"]]} for c in llm.calls])
    # user data amounts seeded: 3000.00 / 5000.00 / 2000.00 / 10000.00 / 6000.00 / 900.00
    for amount in ("3000", "5000.00", "2000.00", "10000", "6000.00", "900.00", "Wynagrodzenie"):
        assert amount not in sent, amount
    run = anna_client.get(f"/api/agent/runs/{r.json()['run_id']}").json()
    tools_used = {s["name"] for s in run["steps"] if s["kind"] == "tool"}
    assert not tools_used & {
        "get_portfolio",
        "get_net_worth",
        "get_month_analysis",
        "get_investment_profile",
    }
