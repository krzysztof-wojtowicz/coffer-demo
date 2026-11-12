import json
from collections.abc import Iterator

import pytest
import requests
import yfinance
from sqlalchemy import select

from coffer.agent.investment.schemas import DISCLAIMER
from coffer.agent.llm import LLMUnavailable, get_llm_client
from coffer.agent.models import AgentRun
from coffer.agent.testing import FakeLLM
from coffer.core.config import get_settings
from coffer.main import app
from coffer.market import service as market
from coffer.profile.models import InvestmentProfile
from tests.market.conftest import FakeYF

URL = "/api/agent/investment/advice"
HOLDINGS = {
    "holdings": [
        {"symbol": "AAPL", "asset_class": "stocks", "quantity": "10", "current_value": "7500.00"},
        {"symbol": None, "asset_class": "deposit", "quantity": "1", "current_value": "2500.00"},
    ]
}


@pytest.fixture(autouse=True)
def fake_yf(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeYF]:
    fake = FakeYF()
    monkeypatch.setattr(yfinance, "Ticker", fake.ticker)
    monkeypatch.setattr(market, "_source_reachable", lambda: fake.reachable)
    market.clear_cache()
    yield fake
    market.clear_cache()


@pytest.fixture
def use_llm():
    def _use(llm):
        app.dependency_overrides[get_llm_client] = lambda: llm
        return llm

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture
def set_profile(db, user):
    def _set(risk: str, horizon: str = "long", preferred: list[str] | None = None) -> None:
        db.add(
            InvestmentProfile(
                user_id=user.id, horizon=horizon, risk=risk, preferred_classes=preferred or []
            )
        )
        db.commit()

    return _set


def call(tool: str, args: dict | None = None) -> str:
    return json.dumps({"action": "call_tool", "tool": tool, "args": args or {}})


def final(picks: list[dict]) -> str:
    return json.dumps({"action": "final", "answer": {"top_picks": picks}})


LLM_PICKS = [
    {
        "name": "Vanguard Total World Stock ETF",
        "asset_class": "etf",
        "symbol": "VT",
        "rationale": "Szeroka dywersyfikacja globalna.",
        "risk_level": 3,
        "source_url": "https://example.com/a",
    },
    {
        "name": "Vanguard Total Bond Market ETF",
        "asset_class": "bond",
        "symbol": "BND",
        "rationale": "Stabilizuje portfel.",
        "risk_level": 2,
        "source_url": "https://hallucinated.example/x",
    },
    {
        "name": "SPDR Gold Shares",
        "asset_class": "commodity",
        "symbol": "GLD",
        "rationale": "Zabezpieczenie przed inflacją.",
        "risk_level": 3,
    },
]


def test_requires_auth(client, use_llm):
    use_llm(None)
    assert client.post(URL, json=HOLDINGS).status_code == 401


def test_fallback_without_llm_default_profile(auth_client, use_llm):
    use_llm(None)
    r = auth_client.post(URL, json=HOLDINGS)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is False
    assert body["disclaimer"] == DISCLAIMER and "nie jest porada" in body["disclaimer"]
    picks = body["top_picks"]
    assert len(picks) == 3
    assert len({p["asset_class"] for p in picks}) == 3
    assert all(p["risk_level"] <= 3 for p in picks)  # default: moderate
    held = {"stock", "cash"}
    assert not held & {p["asset_class"] for p in picks}  # diversifies away from holdings
    assert all(p["rationale"] for p in picks)
    assert body["tips"][0] == {
        "title": "Rynki rosną",
        "summary": "Indeksy w górę",
        "source": "Reuters",
        "url": "https://example.com/a",
    }


def test_fallback_respects_low_risk(auth_client, use_llm, set_profile):
    use_llm(None)
    set_profile("low")
    picks = auth_client.post(URL, json={"holdings": []}).json()["top_picks"]
    assert len(picks) == 3 and all(p["risk_level"] <= 2 for p in picks)


def test_fallback_high_risk_prefers_classes(auth_client, use_llm, set_profile):
    use_llm(None)
    set_profile("high", preferred=["crypto"])
    picks = auth_client.post(URL, json={"holdings": []}).json()["top_picks"]
    assert "crypto" in {p["asset_class"] for p in picks}


def test_fallback_deterministic(auth_client, use_llm):
    use_llm(None)
    a = auth_client.post(URL, json=HOLDINGS).json()["top_picks"]
    b = auth_client.post(URL, json=HOLDINGS).json()["top_picks"]
    assert a == b


def test_tool_calling_loop(auth_client, use_llm):
    llm = use_llm(
        FakeLLM(
            [
                call("get_instrument_universe"),
                call("get_market_tips", {"limit": 3}),
                final(LLM_PICKS),
            ]
        )
    )
    r = auth_client.post(URL, json=HOLDINGS)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is True
    picks = body["top_picks"]
    assert [p["symbol"] for p in picks] == ["VT", "BND", "GLD"]
    assert picks[0]["source_url"] == "https://example.com/a"  # seen in tool output
    assert picks[1]["source_url"] == "https://finance.yahoo.com/quote/BND"  # not hallucinated
    assert len(llm.calls) == 3
    assert all(c["response_schema"]["properties"]["action"] for c in llm.calls)
    last_msgs = llm.calls[2]["messages"]
    assert "Wynik narzędzia get_instrument_universe" in last_msgs[2].content
    assert "Wynik narzędzia get_market_tips" in last_msgs[4].content


def test_only_aggregates_sent_to_llm(auth_client, use_llm):
    llm = use_llm(FakeLLM([final(LLM_PICKS)]))
    auth_client.post(URL, json=HOLDINGS)
    blob = llm.calls[0]["system"] + "".join(m.content for m in llm.calls[0]["messages"])
    assert "user@example.com" not in blob
    assert "7500" not in blob and "2500" not in blob  # no amounts, only shares
    assert '"stock": "75.0"' in blob and "AAPL" in blob


def test_quotes_tool_in_loop(auth_client, use_llm):
    llm = use_llm(FakeLLM([call("get_quotes", {"symbols": ["AAPL"]}), final(LLM_PICKS)]))
    assert auth_client.post(URL, json=HOLDINGS).json()["llm_used"] is True
    assert "190.13" in llm.calls[1]["messages"][-1].content


@pytest.mark.parametrize(
    "responses",
    [
        [LLMUnavailable("down")],
        ["nie json"],
        [final(LLM_PICKS[:2])],
        [call("unknown_tool")] * 4,
        [call("get_instrument_universe")] * 4,
        [final([{**LLM_PICKS[0], "symbol": "BTC-USD", "asset_class": "etf"}, *LLM_PICKS[1:]])],
    ],
)
def test_llm_failures_fall_back(auth_client, use_llm, set_profile, responses):
    set_profile("medium")
    use_llm(FakeLLM(responses))
    r = auth_client.post(URL, json=HOLDINGS)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is False and len(body["top_picks"]) == 3


def test_market_down_still_works(auth_client, use_llm, fake_yf):
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    fake_yf.news_fail = requests.exceptions.ConnectionError("down")
    use_llm(FakeLLM([call("get_quotes", {"symbols": ["AAPL"]}), final(LLM_PICKS)]))
    body = auth_client.post(URL, json=HOLDINGS).json()
    assert body["llm_used"] is True and body["tips"] == []


def test_invalid_holdings_422(auth_client, use_llm):
    use_llm(None)
    bad = {"holdings": [{"asset_class": "etf", "quantity": "-1"}]}
    assert auth_client.post(URL, json=bad).status_code == 422


def test_large_current_value_accepted(auth_client, use_llm):
    use_llm(None)
    body = {
        "holdings": [
            {
                "symbol": "AAPL",
                "asset_class": "stocks",
                "quantity": "1",
                "current_value": "123456789012345.00",
            }
        ]
    }
    assert auth_client.post(URL, json=body).status_code == 200


# --- agent_runs trace and shared daily limit (data-model decision (f)) ---------------


def _runs(db, user_id: int) -> list[AgentRun]:
    db.expire_all()
    return list(
        db.scalars(select(AgentRun).where(AgentRun.user_id == user_id).order_by(AgentRun.id))
    )


def test_advice_run_is_recorded(auth_client, use_llm, db, user):
    use_llm(FakeLLM([call("get_quotes", {"symbols": ["AAPL"]}), final(LLM_PICKS)]))
    body = auth_client.post(URL, json=HOLDINGS).json()
    assert body["llm_used"] is True and body["ai_status"] == "ok"
    (run,) = _runs(db, user.id)
    assert (run.task, run.status, run.attempts, run.model) == ("advisor", "ok", 2, "fake")
    assert run.prompt_version == "advisor_v1"
    assert [c["name"] for c in run.tool_calls] == ["get_quotes"]
    assert len(run.raw_outputs) == 2


def test_advice_suggestion_is_in_history(auth_client, use_llm, db, user):
    use_llm(FakeLLM([call("get_quotes", {"symbols": ["AAPL"]}), final(LLM_PICKS)]))
    body = auth_client.post(URL, json=HOLDINGS).json()
    (item,) = auth_client.get("/api/agent/suggestions").json()
    assert item["type"] == "advisor" and item["month"] is None
    assert len(item["rationale"]) == 3
    assert body["run_id"] is not None
    assert auth_client.get(f"/api/agent/runs/{body['run_id']}").json()["task"] == "advisor"


def test_advice_suggestion_hidden_from_other_user(auth_client, other_auth_client, use_llm):
    use_llm(FakeLLM([final(LLM_PICKS)]))
    auth_client.post(URL, json=HOLDINGS)
    assert other_auth_client.get("/api/agent/suggestions").json() == []


def test_advice_fallback_saves_no_suggestion(auth_client, use_llm):
    use_llm(FakeLLM([LLMUnavailable("down")]))
    auth_client.post(URL, json=HOLDINGS)
    assert auth_client.get("/api/agent/suggestions").json() == []


def test_advice_unavailable_is_recorded(auth_client, use_llm, db, user):
    use_llm(FakeLLM([LLMUnavailable("Gemini status 503")]))
    body = auth_client.post(URL, json=HOLDINGS).json()
    assert body["llm_used"] is False and body["ai_status"] == "unavailable"
    (run,) = _runs(db, user.id)
    assert (run.status, run.attempts, run.error) == ("unavailable", 1, "Gemini status 503")


def test_advice_without_llm_records_nothing(auth_client, use_llm, db, user):
    use_llm(None)
    assert auth_client.post(URL, json=HOLDINGS).json()["ai_status"] == "unavailable"
    assert _runs(db, user.id) == []


def test_advice_daily_limit_shared_with_surplus(auth_client, use_llm, db, user, monkeypatch):
    """N runs (any task) used up -> request N+1 gets rule-based picks, no model call."""
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 2)
    db.add(
        AgentRun(
            user_id=user.id, task="surplus", prompt_version="surplus_v2", status="ok", attempts=1
        )
    )
    db.commit()
    use_llm(FakeLLM([final(LLM_PICKS)]))
    assert auth_client.post(URL, json=HOLDINGS).json()["ai_status"] == "ok"  # run 2 of 2

    llm = use_llm(FakeLLM([final(LLM_PICKS)]))
    r = auth_client.post(URL, json=HOLDINGS)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is False and body["ai_status"] == "limited"
    assert len(body["top_picks"]) == 3
    assert llm.calls == []
    runs = _runs(db, user.id)
    assert runs[-1].status == "limited" and runs[-1].attempts == 0


# --- advisor time budget (COFFER_ADVISOR_TIMEOUT_S) ------------------------------------


class SlowLLM(FakeLLM):
    """Each call 'takes' `seconds` on an injected clock: no real waiting."""

    def __init__(self, responses, now: list[float], seconds: float):
        super().__init__(responses)
        self.now, self.seconds = now, seconds

    def complete(self, **kwargs):
        self.now[0] += self.seconds
        return super().complete(**kwargs)


@pytest.fixture
def fake_clock(monkeypatch) -> list[float]:
    now = [1000.0]
    monkeypatch.setattr("coffer.agent.llm._clock", lambda: now[0])
    return now


def test_advice_timeout_returns_rules(auth_client, use_llm, db, user, monkeypatch, fake_clock):
    monkeypatch.setattr(get_settings(), "advisor_timeout_s", 60)
    steps = [call("get_instrument_universe"), call("get_quotes", {"symbols": ["VT"]})]
    llm = use_llm(SlowLLM([*steps, final(LLM_PICKS)], fake_clock, seconds=40))
    r = auth_client.post(URL, json=HOLDINGS)
    assert r.status_code == 200
    body = r.json()
    assert body["llm_used"] is False and body["ai_status"] == "timeout"
    assert len(body["top_picks"]) == 3
    assert len(llm.calls) == 2  # third step not started: 80 s > 60 s budget
    (run,) = _runs(db, user.id)
    assert (run.status, run.attempts) == ("timeout", 2)


def test_advice_within_budget_ok(auth_client, use_llm, monkeypatch, fake_clock):
    monkeypatch.setattr(get_settings(), "advisor_timeout_s", 60)
    use_llm(SlowLLM([call("get_instrument_universe"), final(LLM_PICKS)], fake_clock, seconds=20))
    assert auth_client.post(URL, json=HOLDINGS).json()["ai_status"] == "ok"
