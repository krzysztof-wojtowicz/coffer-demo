import json
import threading
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from coffer.agent import guard as guard_module
from coffer.agent.actions.portfolio_review import PORTFOLIO_REVIEW, NoParams
from coffer.agent.guard import ActionRateLimited, guard
from coffer.agent.models import AgentRun
from coffer.agent.runner import ActionFailed, run_action
from coffer.agent.schemas import ActionReport, Recommendation, Source
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry

from . import fakes
from .conftest import final, step


def _boom(db, user):
    return _run(
        db, user, action=fakes.ACTION, params=fakes.Params(explode=True), registry=fakes.registry()
    )


def _run(db, user, llm=None, action=PORTFOLIO_REVIEW, params=None, registry=None):
    return run_action(
        db, user.id, action, params or NoParams(), llm, registry or default_registry()
    )


# --- (2) abuse guard ------------------------------------------------------------------------


def test_guard_call_budget_per_user(db, user, make_user, monkeypatch):
    monkeypatch.setattr(guard_module, "WINDOWS", ((3, 60.0),))
    for _ in range(3):
        assert _run(db, user).ai_status == "no_data"
    with pytest.raises(ActionRateLimited) as exc:
        _run(db, user)
    assert exc.value.retry_after >= 1
    assert db.scalars(select(AgentRun)).all().__len__() == 3  # the rejected call left no trace
    other = make_user(email="inny@example.com")
    assert _run(db, other).ai_status == "no_data"  # budgets are per user


def test_guard_window_slides():
    now = [0.0]
    g = guard_module.ActionGuard(clock=lambda: now[0])
    original = guard_module.WINDOWS
    guard_module.WINDOWS = ((2, 10.0),)
    try:
        for _ in range(2):
            g.acquire(1)
            g.release(1)
        with pytest.raises(ActionRateLimited):
            g.acquire(1)
        now[0] = 11.0
        g.acquire(1)
    finally:
        guard_module.WINDOWS = original


def test_guard_parallel_cap_and_release_on_error(db, user, monkeypatch):
    monkeypatch.setattr(guard_module, "MAX_PARALLEL", 2)
    guard.acquire(user.id)
    guard.acquire(user.id)
    with pytest.raises(ActionRateLimited):
        _run(db, user)
    guard.release(user.id)
    assert _run(db, user).ai_status == "no_data"  # a free slot again, released after the run
    guard.release(user.id)
    # a crashing run frees its slot as well
    with pytest.raises(ActionFailed):
        _run(
            db,
            user,
            action=fakes.ACTION,
            params=fakes.Params(explode=True),
            registry=fakes.registry(),
        )
    assert guard._running.get(user.id) is None


def test_guard_thread_safety(user):
    ok, blocked = [], []

    def go():
        try:
            guard.acquire(user.id)
            ok.append(1)
        except ActionRateLimited:
            blocked.append(1)

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(ok) == guard_module.MAX_PARALLEL and len(blocked) == 8 - len(ok)


def test_api_returns_429(client, user, monkeypatch):
    from tests.conftest import login_as

    monkeypatch.setattr(guard_module, "WINDOWS", ((1, 60.0),))
    c = login_as(client, user)
    url = "/api/agent/actions/portfolio_review/run"
    assert c.post(url, json={"params": {}}).status_code == 200
    r = c.post(url, json={"params": {}})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert "Zbyt wiele" in r.json()["detail"]
    sse = c.post(url, json={"params": {}}, headers={"accept": "text/event-stream"})
    assert "event: error" in sse.text and "Zbyt wiele" in sse.text


# --- (3) time budget before tools ------------------------------------------------------------


def test_no_tool_call_after_deadline(db, profile, user, monkeypatch):
    left = iter([30.0, -1.0])
    monkeypatch.setattr("coffer.agent.runner.remaining_s", lambda: next(left, -1.0))
    call = step("call_tool", tool="target_allocation", args={"risk": "low", "horizon": "short"})
    out = _run(db, user, FakeLLM([call, final()]))
    assert out.ai_status == "timeout" and out.source == "rules" and out.report.findings
    steps = db.scalars(select(AgentRun)).one().steps
    assert not [s for s in steps if s["kind"] == "tool" and s["origin"] == "model"]


# --- (4) no internals in run.error -----------------------------------------------------------


def test_error_column_has_only_exception_type(db, user):
    with pytest.raises(ActionFailed):
        _run(
            db,
            user,
            action=fakes.ACTION,
            params=fakes.Params(explode=True),
            registry=fakes.registry(),
        )
    run = db.scalars(select(AgentRun)).one()
    assert run.status == "error" and run.error == "RuntimeError"
    assert "exploded" not in json.dumps(run.steps)  # the message stays in the log only


# --- (5) links ---------------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "ftp://x/y", "//x"])
def test_bad_links_rejected(url):
    with pytest.raises(ValueError):
        Recommendation(title="x", source_url=url)
    with pytest.raises(ValueError):
        Source(title="x", url=url, fetched_at=datetime.now(UTC))
    assert Recommendation(title="x", source_url="HTTPS://example.com").source_url


def test_old_rows_do_not_break_reading():
    stored = {
        "headline": "Stary wynik",
        "sources": [
            {"title": "ok", "url": "https://a.example", "fetched_at": "2025-01-01T00:00:00Z"},
            {"title": "zły", "url": "javascript:alert(1)", "fetched_at": "2025-01-01T00:00:00Z"},
        ],
        "recommendations": [{"title": "R", "source_url": "javascript:x"}, {"title": "S"}],
    }
    report = ActionReport.model_validate(stored)
    assert [s.url for s in report.sources] == ["https://a.example"]
    assert [r.source_url for r in report.recommendations] == [None, None]


def test_tool_news_with_bad_scheme_get_no_url(db, user, monkeypatch):
    from coffer.agent.tools.registry import ToolContext
    from coffer.market import service as market_service
    from coffer.market.service import MarketTip

    now = datetime.now(UTC)
    tips = [MarketTip("A", "s", "P", "javascript:alert(1)", now, now)]
    monkeypatch.setattr(market_service, "get_company_news", lambda s, limit=5: tips)
    call = default_registry().call(
        "get_company_news", {"symbol": "AAPL"}, ToolContext(db=db, user_id=user.id, now=now)
    )
    assert call.output["news"][0]["url"] is None


# --- SSE does not hold the request session ----------------------------------------------------


def test_sse_closes_request_session_before_streaming(client, user, monkeypatch):
    from sqlalchemy.orm import Session

    from coffer.agent import api as agent_api
    from tests.conftest import login_as

    closed: list[int] = []
    original_close = Session.close

    def tracking_close(self):
        closed.append(1)
        return original_close(self)

    seen_at_stream: list[int] = []
    original_stream = agent_api.stream_events

    def spy(work):
        seen_at_stream.append(len(closed))
        return original_stream(work)

    c = login_as(client, user)
    monkeypatch.setattr(Session, "close", tracking_close)
    monkeypatch.setattr(agent_api, "stream_events", spy)
    r = c.post(
        "/api/agent/actions/portfolio_review/run",
        json={"params": {}},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200 and "event: result" in r.text
    assert seen_at_stream and seen_at_stream[0] >= 1  # closed before the response was built
