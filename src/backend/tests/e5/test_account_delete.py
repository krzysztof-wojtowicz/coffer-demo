from sqlalchemy import text

from coffer.agent.testing import FakeLLM
from tests.e5.conftest import final_answer, run_action_api

TABLES = ("agent_runs", "suggestions", "llm_usage_daily", "budget_limits")


def _count(db, table, uid):
    return db.execute(text(f"SELECT count(*) FROM {table} WHERE user_id = :u"), {"u": uid}).scalar()


def test_delete_account_cleans_stage5_tables(anna_client, anna, bob, bob_client, use_llm, db):
    from sqlalchemy import select

    from coffer.transactions.models import Category

    use_llm(FakeLLM([final_answer("portfolio_review")] * 2))
    cat = db.scalars(select(Category).where(Category.in_budget.is_(True))).first()
    for c in (anna_client, bob_client):
        assert run_action_api(c, "portfolio_review").json()["ai_status"] == "ok"
        assert c.put(f"/api/budget/limits/{cat.id}", json={"amount": "100.00"}).status_code == 200
    uid, bid = anna.id, bob.id
    db.expire_all()
    for t in TABLES:
        assert _count(db, t, uid) >= 1, t
    r = anna_client.request("DELETE", "/api/auth/account", json={"password": "haslo12345"})
    assert r.status_code == 204, r.text
    db.expire_all()
    for t in TABLES:
        assert _count(db, t, uid) == 0, t
        assert _count(db, t, bid) >= 1, f"{t}: other user's rows must stay"
