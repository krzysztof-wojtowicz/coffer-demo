import pytest

from coffer.agent.llm import LLMTimeout, LLMUnavailable
from coffer.agent.testing import FakeLLM
from coffer.core.config import get_settings
from tests.e5.conftest import ACTION_CASES, final_answer, run_action_api

IDS = [a for a, _ in ACTION_CASES]


def _assert_rules_result(client, r, expected_status):
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["ai_status"] == expected_status, b
    assert b["source"] == "rules"
    rep = b["report"]
    assert rep["headline"].strip()
    assert rep["disclaimer"].strip()  # F33
    assert rep["findings"] or rep["facts"] or rep["tables"]
    assert b["suggestion_id"] is not None
    s = client.get(f"/api/agent/suggestions/{b['suggestion_id']}").json()
    assert s["source"] == "rules" and s["ai_status"] == expected_status
    assert s["id"] in {
        i["id"] for i in client.get("/api/agent/suggestions?limit=50").json()["items"]
    }


@pytest.mark.parametrize(("action", "params"), ACTION_CASES, ids=IDS)
def test_no_llm(anna_client, use_llm, action, params):
    use_llm(None)
    _assert_rules_result(anna_client, run_action_api(anna_client, action, params), "unavailable")


@pytest.mark.parametrize(("action", "params"), ACTION_CASES, ids=IDS)
def test_llm_unavailable(anna_client, use_llm, action, params):
    use_llm(FakeLLM([LLMUnavailable("down")] * 3))
    _assert_rules_result(anna_client, run_action_api(anna_client, action, params), "unavailable")


@pytest.mark.parametrize(("action", "params"), ACTION_CASES, ids=IDS)
def test_llm_timeout(anna_client, use_llm, action, params):
    use_llm(FakeLLM([LLMTimeout("slow")] * 3))
    _assert_rules_result(anna_client, run_action_api(anna_client, action, params), "timeout")


@pytest.mark.parametrize(("action", "params"), ACTION_CASES, ids=IDS)
def test_two_invalid_answers(anna_client, use_llm, action, params):
    bad = final_answer(action, headline="Zysk wyniesie 777777.77 zl")
    use_llm(FakeLLM([bad] * 5))
    _assert_rules_result(anna_client, run_action_api(anna_client, action, params), "invalid")


@pytest.mark.parametrize(("action", "params"), ACTION_CASES, ids=IDS)
def test_daily_limit_exhausted(anna_client, use_llm, monkeypatch, action, params):
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 1)
    use_llm(FakeLLM([final_answer(action)] * 5))
    first = run_action_api(anna_client, "portfolio_review")
    assert first.json()["ai_status"] == "ok"
    _assert_rules_result(anna_client, run_action_api(anna_client, action, params), "limited")


@pytest.mark.parametrize(("action", "params"), ACTION_CASES, ids=IDS)
def test_ok_with_model_is_source_ai(anna_client, use_llm, action, params):
    use_llm(FakeLLM([final_answer(action)] * 3))
    b = run_action_api(anna_client, action, params).json()
    errs = anna_client.get(f"/api/agent/runs/{b['run_id']}").json()["validation_errors"]
    if action in ("investment_ideas", "company_research"):
        # these actions require 2-5 recommendations (action-specific check): model answer
        # without them is rejected and falls back to rules
        assert b["ai_status"] in ("ok", "invalid"), errs
        return
    assert b["ai_status"] == "ok" and b["source"] == "ai", errs
    assert b["report"]["disclaimer"].strip()


@pytest.mark.parametrize("action", ["investment_ideas", "company_research"])
def test_sources_have_url_and_fetched_at(anna_client, use_llm, action):
    use_llm(None)
    params = dict(ACTION_CASES)[action]
    rep = run_action_api(anna_client, action, params).json()["report"]
    assert rep["sources"], "N07/F35: market actions must cite sources"
    for s in rep["sources"]:
        assert s["url"].startswith("http") and s["fetched_at"]
