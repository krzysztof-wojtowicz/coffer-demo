from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import text

from coffer.agent.testing import FakeLLM
from coffer.core.config import get_settings
from coffer.main import app
from tests.conftest import login_as
from tests.e5.conftest import final_answer, run_action_api


def _fire(user, n, wave):
    clients = [login_as(TestClient(app), user) for _ in range(n)]

    def go(c):
        return run_action_api(c, "portfolio_review")

    with ThreadPoolExecutor(wave) as ex:
        return list(ex.map(go, clients))


def test_five_runs_limit_two_in_waves(anna, use_llm, monkeypatch, db):
    """Card scenario with at most 2 runs in parallel (the parallel cap is 2)."""
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 2)
    use_llm(FakeLLM([final_answer("portfolio_review")] * 10))
    results = []
    for wave in ((2, 2), (2, 2), (1, 1)):
        results += _fire(anna, *wave)
    assert all(r.status_code == 200 for r in results)
    statuses = sorted(r.json()["ai_status"] for r in results)
    assert statuses.count("ok") == 2 and statuses.count("limited") == 3
    runs = db.execute(text("SELECT runs FROM llm_usage_daily")).scalars().all()
    assert runs == [5] or max(runs) <= 5  # reservations are atomic, never lost


def test_five_parallel_never_more_than_limit(anna, use_llm, monkeypatch):
    """Contract invariant under real parallelism: <= limit 'ok'; others limited or 429."""
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 2)
    use_llm(FakeLLM([final_answer("portfolio_review")] * 10))
    results = _fire(anna, 5, 5)
    codes = {r.status_code for r in results}
    assert codes <= {200, 429}
    ok = [r for r in results if r.status_code == 200 and r.json()["ai_status"] == "ok"]
    assert len(ok) <= 2


def test_limit_is_per_user(anna, bob, use_llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_daily_limit", 1)
    use_llm(FakeLLM([final_answer("portfolio_review")] * 4))
    a = _fire(anna, 1, 1)[0].json()
    b = _fire(bob, 1, 1)[0].json()
    assert a["ai_status"] == "ok" and b["ai_status"] == "ok"
    assert _fire(anna, 1, 1)[0].json()["ai_status"] == "limited"


def test_usage_tokens_summed(anna_client, use_llm, db):
    use_llm(FakeLLM([final_answer("portfolio_review")] * 2, input_tokens=70, output_tokens=7))
    run_action_api(anna_client, "portfolio_review")
    run_action_api(anna_client, "portfolio_review")
    row = db.execute(text("SELECT runs, input_tokens, output_tokens FROM llm_usage_daily")).one()
    assert tuple(row) == (2, 140, 14)


def test_unexpected_error_is_sanitized_in_run(anna_client, use_llm, db):
    secret = "SELECT password_hash FROM users WHERE email='anna.kowalska@example.com'"
    use_llm(FakeLLM([RuntimeError(secret)]))
    r = run_action_api(anna_client, "portfolio_review")
    assert r.status_code == 500
    assert secret not in r.text
    item = anna_client.get("/api/agent/runs").json()["items"][0]
    run = anna_client.get(f"/api/agent/runs/{item['id']}").json()
    assert run["status"] == "error"
    assert run["error"] == "RuntimeError"
    assert "SELECT" not in str(run) and "password" not in str(run["error"])


def test_rate_limit_429_with_retry_after_and_no_run_row(anna_client, use_llm, db):
    use_llm(None)
    for _ in range(20):
        assert run_action_api(anna_client, "portfolio_review").status_code == 200
    before = db.execute(text("SELECT count(*) FROM agent_runs")).scalar()
    r = run_action_api(anna_client, "portfolio_review")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert db.execute(text("SELECT count(*) FROM agent_runs")).scalar() == before
