from datetime import UTC, datetime
from decimal import Decimal

import pytest

from coffer.agent.models import AgentRun, Suggestion

URL = "/api/agent/runs"


@pytest.fixture
def make_run(db):
    def _make(user, **kw):
        fields = {
            "user_id": user.id,
            "task": "portfolio_review",
            "prompt_version": "portfolio_review_v1",
            "status": "ok",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "llm_calls": 1,
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": Decimal("0.001000"),
            "duration_ms": 500,
            "tool_calls": [{"name": "a"}, {"name": "b"}],
            "steps": [{"index": 0, "kind": "tool"}],
            "messages": [{"role": "system", "content": "s"}],
            "created_at": datetime(2025, 3, 10, 12, 0, tzinfo=UTC),
            **kw,
        }
        run = AgentRun(**fields)
        db.add(run)
        db.commit()
        return run

    return _make


def ids(r) -> list[int]:
    return [i["id"] for i in r.json()["items"]]


def test_list_shape(auth_client, user, make_run, db):
    run = make_run(user)
    db.add(
        Suggestion(
            user_id=user.id,
            agent_run_id=run.id,
            type="portfolio_review",
            summary="s",
            report={},
            disclaimer="d",
            model="m",
            data_snapshot={},
        )
    )
    db.commit()
    body = auth_client.get(URL).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item == {
        "id": run.id,
        "action": "portfolio_review",
        "status": "ok",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "llm_calls": 1,
        "tool_calls_count": 2,
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": "0.001000",
        "duration_ms": 500,
        "created_at": "2025-03-10T12:00:00Z",
        "suggestion_id": 1,
    }


def test_filters(auth_client, user, make_run):
    a = make_run(user, task="portfolio_review", status="ok", provider="openai")
    b = make_run(user, task="savings_analysis", status="invalid", provider="gemini")
    c = make_run(user, task="portfolio_review", status="timeout", provider=None)
    assert sorted(ids(auth_client.get(URL, params={"action": "portfolio_review"}))) == [a.id, c.id]
    assert ids(auth_client.get(URL, params={"status": "invalid"})) == [b.id]
    assert ids(auth_client.get(URL, params={"provider": "gemini"})) == [b.id]
    assert auth_client.get(URL, params={"action": "none"}).json() == {"items": [], "total": 0}


def test_date_range_is_inclusive(auth_client, user, make_run):
    early = make_run(user, created_at=datetime(2025, 3, 1, 0, 0, tzinfo=UTC))
    late = make_run(user, created_at=datetime(2025, 3, 31, 23, 59, tzinfo=UTC))
    got = lambda **p: sorted(ids(auth_client.get(URL, params=p)))  # noqa: E731
    assert got(date_from="2025-03-01", date_to="2025-03-01") == [early.id]
    assert got(date_from="2025-03-31") == [late.id]
    assert got(date_to="2025-03-31") == [early.id, late.id]
    assert got(date_from="2025-04-01") == []


def test_sorting_and_nulls_last(auth_client, user, make_run):
    slow = make_run(user, duration_ms=900, cost_usd=Decimal("0.5"), input_tokens=1, output_tokens=1)
    fast = make_run(
        user, duration_ms=100, cost_usd=Decimal("0.1"), input_tokens=500, output_tokens=0
    )
    unknown = make_run(user, duration_ms=None, cost_usd=None, input_tokens=None, output_tokens=None)
    g = lambda **p: ids(auth_client.get(URL, params=p))  # noqa: E731
    assert g(sort="duration_ms", order="desc") == [slow.id, fast.id, unknown.id]
    assert g(sort="duration_ms", order="asc") == [fast.id, slow.id, unknown.id]
    assert g(sort="cost_usd", order="desc") == [slow.id, fast.id, unknown.id]
    assert g(sort="tokens", order="desc") == [fast.id, slow.id, unknown.id]


def test_default_order_newest_first_and_paging(auth_client, user, make_run):
    runs = [make_run(user, created_at=datetime(2025, 3, d, tzinfo=UTC)) for d in (1, 2, 3, 4, 5)]
    newest_first = [r.id for r in reversed(runs)]
    assert ids(auth_client.get(URL)) == newest_first
    page = auth_client.get(URL, params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 5 and [i["id"] for i in page["items"]] == newest_first[2:4]
    assert ids(auth_client.get(URL, params={"order": "asc"})) == newest_first[::-1]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"sort": "nope"},
        {"order": "up"},
        {"date_from": "x"},
    ],
)
def test_bad_query_params(auth_client, params):
    assert auth_client.get(URL, params=params).status_code == 422


def test_user_isolation(auth_client, other_auth_client, user, make_run, db):
    run = make_run(user)
    assert auth_client.get(URL).json()["total"] == 1
    assert other_auth_client.get(URL).json() == {"items": [], "total": 0}
    r = other_auth_client.get(f"{URL}/{run.id}")
    assert r.status_code == 404 and r.json()["detail"] == "Nie znaleziono przebiegu agenta"


def test_run_detail(auth_client, user, make_run):
    run = make_run(user, params={"x": 1}, raw_outputs=["{}"], validation_errors=["e"], error="boom")
    body = auth_client.get(f"{URL}/{run.id}").json()
    assert body["id"] == run.id and body["tool_calls_count"] == 2
    assert body["params"] == {"x": 1} and body["prompt_version"] == "portfolio_review_v1"
    assert body["steps"] == [{"index": 0, "kind": "tool"}]
    assert body["messages"][0]["role"] == "system"
    assert body["raw_outputs"] == ["{}"] and body["validation_errors"] == ["e"]
    assert body["error"] == "boom" and len(body["tool_calls"]) == 2


def test_unknown_run_404(auth_client):
    assert auth_client.get(f"{URL}/999").status_code == 404


def test_legacy_run_has_empty_steps(auth_client, user, make_run):
    run = make_run(user, task="surplus", status="no_surplus", steps=[], provider=None)
    body = auth_client.get(f"{URL}/{run.id}").json()
    assert body["action"] == "surplus" and body["status"] == "no_surplus" and body["steps"] == []
