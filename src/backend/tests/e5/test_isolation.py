import pytest

from coffer.agent.testing import FakeLLM
from tests.e5.conftest import PREV_MONTH, final_answer, run_action_api


def test_new_endpoints_require_session(client):
    gets = [
        "/api/agent/actions",
        "/api/agent/tools",
        "/api/agent/suggestions",
        "/api/agent/suggestions/1",
        "/api/agent/runs",
        "/api/agent/runs/1",
        "/api/agent/status",
        "/api/budget/limits",
        "/api/budget/2025-03/insights",
    ]
    for p in gets:
        assert client.get(p).status_code == 401, p
    assert (
        client.post("/api/agent/actions/portfolio_review/run", json={"params": {}}).status_code
        == 401
    )
    assert client.put("/api/budget/limits/1", json={"amount": "1.00"}).status_code == 401
    assert client.delete("/api/budget/limits/1").status_code == 401


@pytest.fixture
def both_runs(anna_client, bob_client, use_llm):
    use_llm(None)
    a = run_action_api(anna_client, "portfolio_review").json()
    b = run_action_api(bob_client, "savings_analysis", {"month": PREV_MONTH}).json()
    assert a["suggestion_id"] and b["suggestion_id"]
    return a, b


def test_runs_and_suggestions_detail_404(anna_client, bob_client, both_runs):
    a, b = both_runs
    assert anna_client.get(f"/api/agent/runs/{b['run_id']}").status_code == 404
    assert anna_client.get(f"/api/agent/suggestions/{b['suggestion_id']}").status_code == 404
    assert bob_client.get(f"/api/agent/runs/{a['run_id']}").status_code == 404
    assert bob_client.get(f"/api/agent/suggestions/{a['suggestion_id']}").status_code == 404
    assert anna_client.get(f"/api/agent/runs/{a['run_id']}").status_code == 200


FILTERS = [
    "",
    "action=portfolio_review",
    "action=savings_analysis",
    "source=rules",
    "date_from=2000-01-01",
    "date_to=2100-01-01",
    "order=asc",
    "limit=50&offset=0",
]


@pytest.mark.parametrize("flt", FILTERS)
def test_suggestion_lists_only_own(anna_client, bob_client, both_runs, flt):
    a, b = both_runs
    mine = anna_client.get(f"/api/agent/suggestions?{flt}").json()
    ids = {i["id"] for i in mine["items"]}
    assert b["suggestion_id"] not in ids
    assert mine["total"] == len(mine["items"]) <= 1
    theirs = bob_client.get(f"/api/agent/suggestions?{flt}").json()
    assert a["suggestion_id"] not in {i["id"] for i in theirs["items"]}


def test_suggestion_q_search_does_not_cross_users(anna_client, bob_client, both_runs):
    # headline text of bob's run must not be findable by anna
    b_sug = bob_client.get("/api/agent/suggestions").json()["items"][0]
    word = b_sug["headline"].split()[0]
    res = anna_client.get("/api/agent/suggestions", params={"q": word}).json()
    assert b_sug["id"] not in {i["id"] for i in res["items"]}


@pytest.mark.parametrize(
    "flt",
    [
        "",
        "status=unavailable",
        "provider=openai",
        "action=savings_analysis",
        "sort=duration_ms&order=asc",
        "sort=tokens",
        "sort=cost_usd&order=desc",
    ],
)
def test_run_lists_only_own(anna_client, bob_client, both_runs, flt):
    a, b = both_runs
    mine = anna_client.get(f"/api/agent/runs?{flt}").json()
    assert b["run_id"] not in {i["id"] for i in mine["items"]}
    assert mine["total"] <= 1


def test_limits_isolated(anna_client, bob_client, db):
    from sqlalchemy import select

    from coffer.transactions.models import Category

    cat = db.scalars(select(Category).where(Category.in_budget.is_(True))).first()
    assert (
        anna_client.put(f"/api/budget/limits/{cat.id}", json={"amount": "300.00"}).status_code
        == 200
    )
    assert bob_client.get("/api/budget/limits").json() == []
    assert bob_client.delete(f"/api/budget/limits/{cat.id}").status_code == 404
    insights = bob_client.get("/api/budget/2025-03/insights").json()
    assert insights["limits"] == []
    assert len(anna_client.get("/api/budget/limits").json()) == 1


def test_llm_unused_foreign(anna_client, use_llm):
    llm = use_llm(FakeLLM([final_answer("portfolio_review")]))
    assert anna_client.get("/api/agent/runs/999999").status_code == 404
    assert llm.calls == []
