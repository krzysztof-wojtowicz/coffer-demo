import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from coffer.agent.llm import LLMUnavailable, get_llm_client
from coffer.agent.models import AgentRun, Suggestion
from coffer.agent.schemas import DISCLAIMER
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry
from coffer.agent.workflows.surplus import run_surplus
from coffer.core.config import get_settings
from coffer.main import app
from coffer.profile.models import InvestmentProfile

from .conftest import DESCRIPTION, MONTH


def draft(refers_to: str = "budget", value: str = "3765.44", claim: str | None = None) -> str:
    return json.dumps(
        {
            "summary": "Odłóż nadwyżkę w bezpiecznej formie.",
            "rationale": [
                {
                    "claim": claim or "Nadwyżka w tym miesiącu jest dodatnia",
                    "refers_to": refers_to,
                    "value": value,
                }
            ],
            "risks": ["Inflacja może obniżyć realną wartość oszczędności."],
        }
    )


GOOD = draft()
GOOD_PROFILE = draft("profile", "wysoka")
BAD_NUMBER = draft(value="777777.77")


@pytest.fixture
def use_llm():
    def _use(llm):
        app.dependency_overrides[get_llm_client] = lambda: llm
        return llm

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture
def profile(db, surplus_data):
    db.add(
        InvestmentProfile(
            user_id=surplus_data.id,
            horizon="long",
            risk="high",
            preferred_classes=["stocks"],
        )
    )
    db.commit()


def run(db, user_id, llm, month=MONTH, events=None):
    cb = events.append if events is not None else (lambda e: None)
    return run_surplus(db, user_id, month, llm, default_registry(), cb)


def last_run(db) -> AgentRun:
    db.expire_all()
    return db.scalars(select(AgentRun).order_by(AgentRun.id.desc())).first()


def test_success_without_profile(db, surplus_data):
    llm = FakeLLM([GOOD])
    out = run(db, surplus_data.id, llm)
    assert out.ai_status == "ok"
    assert out.summary.surplus == "3765.44"
    s = out.suggestion
    assert s.type == "surplus" and s.month == MONTH
    assert s.rationale[0].refers_to == "budget"
    assert s.rationale[0].value == "3765.44"
    assert s.risks
    assert s.disclaimer == DISCLAIMER
    assert s.model == "fake"
    assert s.profile_used is False
    assert isinstance(s.generated_at, datetime) and s.generated_at.tzinfo is not None
    assert out.run_id is not None
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["system"].strip()
    assert "rationale" in call["response_schema"]["properties"]


def test_success_with_profile(db, surplus_data, profile):
    out = run(db, surplus_data.id, FakeLLM([GOOD_PROFILE]))
    assert out.ai_status == "ok"
    assert out.suggestion.profile_used is True
    row = db.scalars(select(Suggestion)).one()
    assert row.profile_snapshot is not None
    assert row.profile_snapshot["available"] is True
    assert row.profile_snapshot["risk"] == "high"
    assert row.data_snapshot["surplus"] == "3765.44"
    assert row.disclaimer == DISCLAIMER


def test_no_profile_snapshot_null(db, surplus_data):
    run(db, surplus_data.id, FakeLLM([GOOD]))
    assert db.scalars(select(Suggestion)).one().profile_snapshot is None


def test_user_message_contains_tool_outputs(db, surplus_data):
    llm = FakeLLM([GOOD])
    run(db, surplus_data.id, llm)
    msgs = llm.calls[0]["messages"]
    assert msgs[0].role == "user"
    text = msgs[0].content
    for value in ("5000.00", "1234.56", "3765.44", MONTH):
        assert value in text
    assert "get_month_analysis" in text and "get_investment_profile" in text


def test_n03_llm_input_no_personal_data(db, surplus_data):
    llm = FakeLLM([GOOD])
    run(db, surplus_data.id, llm)
    c = llm.calls[0]
    blob = c["system"] + "".join(m.content for m in c["messages"])
    assert surplus_data.email not in blob and "example.com" not in blob
    for part in ("Kowalski", "PL61109010140000071219812874", "Przelew", "Wyplata firma"):
        assert part not in blob
    assert DESCRIPTION not in blob


def test_profile_ref_without_profile_corrected_on_second_attempt(db, surplus_data):
    llm = FakeLLM([GOOD_PROFILE, GOOD])
    out = run(db, surplus_data.id, llm)
    assert out.ai_status == "ok"
    assert len(llm.calls) == 2
    second = llm.calls[1]["messages"]
    assert [m.role for m in second] == ["user", "assistant", "user"]
    assert second[1].content == GOOD_PROFILE
    assert "Odpowiedź nie przeszła walidacji" in second[2].content
    ar = last_run(db)
    assert ar.status == "ok" and ar.attempts == 2
    assert ar.validation_errors
    assert len(ar.raw_outputs) == 2


def test_bad_json_then_good(db, surplus_data):
    llm = FakeLLM(["to nie jest json", GOOD])
    out = run(db, surplus_data.id, llm)
    assert out.ai_status == "ok"
    assert len(llm.calls) == 2


def test_two_bad_answers_unavailable_and_invalid_run(db, surplus_data):
    llm = FakeLLM([BAD_NUMBER, GOOD_PROFILE])
    out = run(db, surplus_data.id, llm)
    assert out.ai_status == "unavailable"
    assert out.suggestion is None
    assert len(llm.calls) == 2  # tylko jedna poprawka
    ar = last_run(db)
    assert ar.status == "invalid" and ar.attempts == 2
    assert ar.validation_errors
    assert ar.raw_outputs == [BAD_NUMBER, GOOD_PROFILE]
    assert db.scalars(select(Suggestion)).all() == []


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "[]",
        json.dumps({"summary": "x"}),
        json.dumps({"summary": "x", "rationale": []}),
        json.dumps({"summary": "", "rationale": []}),
    ],
)
def test_malformed_twice(db, surplus_data, bad):
    llm = FakeLLM([bad, bad])
    out = run(db, surplus_data.id, llm)
    assert out.ai_status == "unavailable"
    assert last_run(db).status == "invalid"


def test_no_surplus(db, user):
    llm = FakeLLM([GOOD])
    out = run(db, user.id, llm)
    assert out.ai_status == "no_surplus"
    assert out.suggestion is None
    assert llm.calls == []
    ar = last_run(db)
    assert ar.status == "no_surplus" and ar.attempts == 0 and ar.task == "surplus"


def test_deficit_no_surplus(db, user, add_tx):
    add_tx(user, "-100.00")
    llm = FakeLLM([GOOD])
    out = run(db, user.id, llm)
    assert out.ai_status == "no_surplus"
    assert out.summary.expenses == "100.00"
    assert llm.calls == []


def test_llm_none(db, surplus_data):
    out = run(db, surplus_data.id, None)
    assert out.ai_status == "unavailable"
    assert out.suggestion is None
    assert out.summary.surplus == "3765.44"


def test_llm_unavailable(db, surplus_data):
    llm = FakeLLM([LLMUnavailable("down")])
    out = run(db, surplus_data.id, llm)
    assert out.ai_status == "unavailable"
    assert out.suggestion is None
    assert len(llm.calls) == 1
    assert last_run(db).status == "unavailable"


def test_daily_limit(db, surplus_data, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 2)
    now = datetime.now(UTC)
    db.add_all(
        [
            AgentRun(
                user_id=surplus_data.id,
                task="surplus",
                prompt_version="surplus_v2",
                status="ok",
                attempts=1,
            ),
            AgentRun(
                user_id=surplus_data.id,
                task="surplus",
                prompt_version="surplus_v2",
                status="ok",
                attempts=1,
            ),
        ]
    )
    db.commit()
    llm = FakeLLM([GOOD])
    out = run(db, surplus_data.id, llm)
    assert out.ai_status == "limited"
    assert out.suggestion is None
    assert llm.calls == []
    assert last_run(db).status == "limited"
    assert now  # noqa: S101


def test_limit_ignores_zero_attempt_old_and_foreign_runs(db, surplus_data, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 2)
    other = make_user(email="other@example.com")
    kw = dict(task="surplus", prompt_version="surplus_v2", status="ok")
    db.add_all(
        [
            AgentRun(user_id=surplus_data.id, attempts=0, **kw),
            AgentRun(
                user_id=surplus_data.id,
                attempts=1,
                created_at=datetime.now(UTC) - timedelta(days=2),
                **kw,
            ),
            AgentRun(user_id=other.id, attempts=1, **kw),
            AgentRun(user_id=other.id, attempts=1, **kw),
        ]
    )
    db.commit()
    out = run(db, surplus_data.id, FakeLLM([GOOD]))
    assert out.ai_status == "ok"


def test_agent_run_trace(db, surplus_data, profile):
    run(db, surplus_data.id, FakeLLM([GOOD_PROFILE]))
    ar = last_run(db)
    assert ar.task == "surplus" and ar.prompt_version == "surplus_v2"
    assert ar.status == "ok" and ar.attempts == 1 and ar.model == "fake"
    assert ar.duration_ms is not None and ar.duration_ms >= 0
    assert [c["name"] for c in ar.tool_calls] == ["get_month_analysis", "get_investment_profile"]
    assert ar.messages[0]["role"] == "system"
    assert ar.messages[1]["role"] == "user"
    assert ar.raw_outputs == [GOOD_PROFILE]
    assert ar.validation_errors == []


def test_n03_agent_run_has_no_personal_data(db, surplus_data):
    run(db, surplus_data.id, FakeLLM([GOOD]))
    ar = last_run(db)
    blob = json.dumps([ar.messages, ar.tool_calls, ar.raw_outputs], ensure_ascii=False)
    assert surplus_data.email not in blob
    assert "Kowalski" not in blob and DESCRIPTION not in blob and "Wyplata firma" not in blob


def test_events_order(db, surplus_data):
    events = []
    run(db, surplus_data.id, FakeLLM([GOOD]), events=events)

    def typ(e):
        return e["type"] if isinstance(e, dict) else e.type

    types = [typ(e) for e in events]
    assert types[0] == "status"
    assert types.index("summary") < types.index("result")
    assert types[-1] == "result" and types.count("result") == 1
    assert types.index("status") < types.index("summary")


def test_events_end_with_result_when_no_surplus(db, user):
    events = []
    run(db, user.id, None, events=events)
    last = events[-1]
    assert (last["type"] if isinstance(last, dict) else last.type) == "result"


def test_retry_emits_status(db, surplus_data):
    events = []
    run(db, surplus_data.id, FakeLLM(["zle", GOOD]), events=events)
    msgs = [
        (e["message"] if isinstance(e, dict) else e.message)
        for e in events
        if (e["type"] if isinstance(e, dict) else e.type) == "status"
    ]
    assert any("Poprawiam" in m for m in msgs)


def test_other_user_data_not_used(db, surplus_data, make_user, add_tx):
    other = make_user(email="other@example.com")
    add_tx(other, "99999.00")
    out = run(db, surplus_data.id, FakeLLM([GOOD]))
    assert out.summary.income == "5000.00"
