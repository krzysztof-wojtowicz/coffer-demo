from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from coffer.agent import service
from coffer.agent.llm import LLMUnavailable
from coffer.agent.models import AgentRun, LlmUsageDaily, Suggestion
from coffer.agent.runner import ActionFailed, response_schema, run_action
from coffer.agent.testing import FakeLLM
from coffer.core.config import Settings

from . import fakes
from .conftest import final, step


@pytest.fixture
def runner_settings(monkeypatch):
    def install(**values):
        s = Settings.model_construct(**values)
        monkeypatch.setattr("coffer.agent.runner.get_settings", lambda: s)
        return s

    return install


@pytest.fixture
def run(db, user):
    def _run(llm, params=None, events=None):
        return run_action(
            db,
            user.id,
            fakes.ACTION,
            fakes.Params(**(params or {})),
            llm,
            fakes.registry(),
            events.append if events is not None else (lambda e: None),
        )

    return _run


def last_run(db) -> AgentRun:
    return db.scalars(select(AgentRun).order_by(AgentRun.id.desc())).first()


def test_ok_path(db, run):
    llm = FakeLLM([final()], provider="ollama", input_tokens=100, output_tokens=20)
    out = run(llm)
    assert out.ai_status == "ok" and out.source == "ai"
    assert out.report.headline == "Portfel jest skoncentrowany w akcjach."
    assert [f.label for f in out.report.facts] == ["Klasy"]  # facts come from prepare
    assert out.provider == "ollama" and out.model == "fake"
    r = last_run(db)
    assert r.status == "ok" and r.task == "test_action" and r.llm_calls == 1
    assert r.input_tokens == 100 and r.output_tokens == 20
    sug = db.scalars(select(Suggestion)).one()
    assert sug.source == "ai" and sug.ai_status == "ok" and sug.agent_run_id == r.id
    assert out.suggestion_id == sug.id and out.run_id == r.id


def test_trace_steps_and_usage(db, user, run):
    llm = FakeLLM(
        [
            step("call_tool", tool="links", args={}),
            final(source_urls=["https://pl.wikipedia.org/wiki/Akcja"]),
        ],
        provider="openai",
        input_tokens=1000,
        output_tokens=500,
    )
    llm._model = "gpt-4o-mini"
    out = run(llm)
    assert out.ai_status == "ok"
    assert [s.url for s in out.report.sources] == ["https://pl.wikipedia.org/wiki/Akcja"]
    assert out.report.sources[0].title == "Hasło"
    steps = last_run(db).steps
    assert [s["kind"] for s in steps] == ["tool", "llm", "tool", "llm", "validation"]
    assert [s["index"] for s in steps] == list(range(5))
    for s in steps:
        assert s["started_ms"] >= 0 and s["duration_ms"] >= 0 and s["status"] in ("ok", "error")
    assert steps[0]["origin"] == "prepare" and steps[2]["origin"] == "model"
    llm_step = steps[1]
    assert llm_step["provider"] == "openai" and llm_step["model"] == "gpt-4o-mini"
    assert (llm_step["input_tokens"], llm_step["output_tokens"]) == (1000, 500)
    assert llm_step["cost_usd"] == "0.000450"
    r = last_run(db)
    assert str(r.cost_usd) == "0.000900" and r.llm_calls == 2
    usage = db.scalars(select(LlmUsageDaily).where(LlmUsageDaily.user_id == user.id)).one()
    assert (usage.runs, usage.input_tokens, usage.output_tokens) == (1, 2000, 1000)


def test_step_events(run):
    events = []
    run(FakeLLM([final()]), events=events)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "status" and kinds[-1] == "result" and "step" in kinds
    first_step = next(e for e in events if e["type"] == "step")["data"]
    assert set(first_step) == {"index", "kind", "name", "status", "duration_ms"}


def test_no_data(db, run):
    llm = FakeLLM([])
    out = run(llm, {"empty": True})
    assert out.ai_status == "no_data" and out.source == "none"
    assert out.report.headline == "Brak danych." and out.suggestion_id is None
    assert llm.calls == []
    assert last_run(db).status == "no_data"
    assert db.scalars(select(Suggestion)).first() is None


def test_unavailable_without_llm(db, run):
    out = run(None)
    assert out.ai_status == "unavailable" and out.source == "rules"
    assert out.report.headline == "Wynik regułowy"
    assert last_run(db).status == "unavailable"
    assert db.scalars(select(Suggestion)).one().source == "rules"
    assert db.scalars(select(LlmUsageDaily)).first() is None  # no model call, no usage


def test_unavailable_when_llm_fails(db, run):
    out = run(FakeLLM([LLMUnavailable("503")]))
    assert out.ai_status == "unavailable" and out.source == "rules"
    r = last_run(db)
    assert r.status == "unavailable" and r.error == "503"
    assert r.steps[-1]["kind"] == "fallback" and r.steps[-1]["reason"] == "unavailable"
    assert any(s["kind"] == "llm" and s["status"] == "error" for s in r.steps)


def test_limited(db, run, runner_settings):
    runner_settings(agent_daily_limit=0, agent_max_attempts=2, agent_timeout_s=60)
    llm = FakeLLM([final()])
    out = run(llm)
    assert out.ai_status == "limited" and out.source == "rules"
    assert llm.calls == []
    assert [s["kind"] for s in last_run(db).steps][-2:] == ["limit", "fallback"]


def test_limit_counts_runs(db, run, runner_settings):
    runner_settings(agent_daily_limit=1, agent_max_attempts=2, agent_timeout_s=60)
    assert run(FakeLLM([final()])).ai_status == "ok"
    assert run(FakeLLM([final()])).ai_status == "limited"


def test_timeout(db, run, monkeypatch, runner_settings):
    runner_settings(agent_daily_limit=50, agent_max_attempts=2, agent_timeout_s=60)
    monkeypatch.setattr("coffer.agent.runner.remaining_s", lambda: -1.0)
    out = run(FakeLLM([final()]))
    assert out.ai_status == "timeout" and out.source == "rules"
    assert last_run(db).status == "timeout"


def test_timeout_from_llm(db, run):
    from coffer.agent.llm import LLMTimeout

    out = run(FakeLLM([LLMTimeout("budget")]))
    assert out.ai_status == "timeout"


def test_invalid_twice_falls_back(db, run):
    llm = FakeLLM([final(headline="Liczba 777777.77 z kosmosu."), "to nie jest json"])
    out = run(llm)
    assert out.ai_status == "invalid" and out.source == "rules"
    assert out.report.headline == "Wynik regułowy"
    r = last_run(db)
    assert r.status == "invalid" and len(r.validation_errors) == 2
    assert "777777.77" in r.validation_errors[0]
    # the model got the validation message before its second try
    assert "nie przeszła walidacji" in llm.calls[1]["messages"][-1].content


def test_invalid_then_corrected(db, run):
    out = run(FakeLLM([final(headline="Liczba 777777.77."), final()]))
    assert out.ai_status == "ok"
    assert last_run(db).llm_calls == 2


def test_action_check_is_applied(run):
    out = run(FakeLLM([final(headline="zakazane"), final(headline="zakazane")]))
    assert out.ai_status == "invalid"


def test_url_and_symbol_outside_tool_results_rejected(run):
    bad_url = final(source_urls=["https://evil.example/x"])
    bad_symbol = final(recommendations=[{"title": "Kup", "symbol": "ZZZZ"}])
    assert run(FakeLLM([bad_url, bad_url])).ai_status == "invalid"
    assert run(FakeLLM([bad_symbol, bad_symbol])).ai_status == "invalid"


def test_tool_outside_action_tools(db, run):
    llm = FakeLLM([step("call_tool", tool="get_portfolio", args={}), final()])
    out = run(llm)
    assert out.ai_status == "ok"
    tool_step = last_run(db).steps[1 + 1]  # prepare tool, llm, then the refused tool
    assert tool_step["name"] == "get_portfolio" and tool_step["status"] == "error"
    assert "nie jest dostępne" in llm.calls[1]["messages"][-1].content


def test_tool_error_does_not_abort(db, run):
    llm = FakeLLM(
        [
            step("call_tool", tool="boom", args={}),
            step("call_tool", tool="crash", args={}),
            step("call_tool", tool="target_allocation", args={"risk": "x", "horizon": "y"}),
            final(),
        ]
    )
    out = run(llm)
    assert out.ai_status == "ok"
    tools = [s for s in last_run(db).steps if s["kind"] == "tool" and s["origin"] == "model"]
    assert [t["status"] for t in tools] == ["error", "error", "error"]
    assert tools[0]["error"] == "Źródło niedostępne."
    assert "secret internals" not in str(tools[1])  # unexpected exceptions are not leaked
    assert "Źródło niedostępne." in llm.calls[1]["messages"][-1].content


def test_step_limit(db, run):
    calls: list[str | Exception] = [step("call_tool", tool="links", args={})] * 4
    out = run(FakeLLM(calls))
    assert out.ai_status == "invalid"
    assert last_run(db).llm_calls == 4


def test_unexpected_error_is_recorded(db, run):
    with pytest.raises(ActionFailed):
        run(FakeLLM([]), {"explode": True})
    r = last_run(db)
    assert (
        r.status == "error" and r.error == "RuntimeError"
    )  # no message, SQL or host in the column
    assert db.scalars(select(Suggestion)).first() is None


def test_response_schema_has_no_dangling_refs():
    from coffer.agent.llm import anthropic_schema, gemini_schema

    schema = response_schema(fakes.ACTION, fakes.registry())
    assert schema["properties"]["tool"]["enum"] == list(fakes.ACTION.tools)
    assert "args" in schema["properties"]
    flat = str(gemini_schema(schema))
    assert "$ref" not in flat and "$defs" not in flat
    assert "findings" in flat
    assert "$defs" in anthropic_schema(schema) and "additionalProperties" in str(
        anthropic_schema(schema)
    )


def test_reserve_run_atomic_limit(db, user):
    now = datetime.now(UTC)
    assert [service.reserve_run(db, user.id, now, 2) for _ in range(3)] == [True, True, False]
    assert service.reserve_run(db, user.id, now, 0) is False
