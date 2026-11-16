from datetime import UTC, datetime

import pytest

from coffer.agent.models import Suggestion
from coffer.agent.testing import FakeLLM

from .conftest import final

URL = "/api/agent/suggestions"


@pytest.fixture
def make_sug(db):
    def _make(user, **kw):
        fields = {
            "user_id": user.id,
            "type": "portfolio_review",
            "summary": "Portfel jest skoncentrowany",
            "report": {"headline": "Portfel jest skoncentrowany", "disclaimer": "d"},
            "source": "ai",
            "ai_status": "ok",
            "disclaimer": "d",
            "model": "gpt-4o-mini",
            "data_snapshot": {},
            "created_at": datetime(2025, 3, 10, 12, 0, tzinfo=UTC),
            **kw,
        }
        s = Suggestion(**fields)
        db.add(s)
        db.commit()
        return s

    return _make


def ids(r) -> list[int]:
    return [i["id"] for i in r.json()["items"]]


def test_default_limit_is_5_and_total(auth_client, user, make_sug):
    made = [make_sug(user, created_at=datetime(2025, 3, d, tzinfo=UTC)) for d in range(1, 8)]
    body = auth_client.get(URL).json()
    assert body["total"] == 7 and len(body["items"]) == 5
    assert [i["id"] for i in body["items"]] == [s.id for s in reversed(made)][:5]
    page2 = auth_client.get(URL, params={"offset": 5}).json()
    assert len(page2["items"]) == 2 and page2["total"] == 7


def test_filters(auth_client, user, make_sug):
    a = make_sug(user, summary="Wydatki na jedzenie", type="savings_analysis")
    b = make_sug(user, source="rules", ai_status="unavailable", summary="100% rabat_x")
    g = lambda **p: ids(auth_client.get(URL, params=p))  # noqa: E731
    assert g(action="savings_analysis") == [a.id]
    assert g(source="rules") == [b.id]
    assert g(q="jedzenie") == [a.id] and g(q="JEDZENIE") == [a.id]
    assert g(q="100%") == [b.id]  # % is not a wildcard
    assert g(q="rabat_") == [b.id] and g(q="rabat_y") == []  # _ is not a wildcard
    assert g(date_from="2025-03-11") == []
    assert sorted(g(date_from="2025-03-10", date_to="2025-03-10")) == [a.id, b.id]


def test_order_asc(auth_client, user, make_sug):
    old = make_sug(user, created_at=datetime(2025, 1, 1, tzinfo=UTC))
    new = make_sug(user, created_at=datetime(2025, 2, 1, tzinfo=UTC))
    assert ids(auth_client.get(URL, params={"order": "asc"})) == [old.id, new.id]
    assert ids(auth_client.get(URL)) == [new.id, old.id]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
        {"source": "x"},
        {"q": "x" * 101},
        {"order": "x"},
    ],
)
def test_bad_params(auth_client, params):
    assert auth_client.get(URL, params=params).status_code == 422


def test_shape(auth_client, user, make_sug):
    s = make_sug(
        user, params={"month": "2025-03"}, provider="openai", profile_snapshot={"risk": "low"}
    )
    item = auth_client.get(f"{URL}/{s.id}").json()
    assert item["id"] == s.id and item["action"] == "portfolio_review"
    assert item["source"] == "ai" and item["ai_status"] == "ok"
    assert item["headline"] == "Portfel jest skoncentrowany"
    assert item["report"]["headline"] == "Portfel jest skoncentrowany"
    assert item["params"] == {"month": "2025-03"} and item["provider"] == "openai"
    assert item["model"] == "gpt-4o-mini" and item["profile_used"] is True
    assert item["run_id"] is None


def test_rules_suggestion_hides_model(auth_client, user, make_sug):
    s = make_sug(user, source="rules", ai_status="invalid", model="rules")
    assert auth_client.get(f"{URL}/{s.id}").json()["model"] is None


def test_foreign_and_unknown_suggestion_404(auth_client, other_auth_client, user, make_sug):
    s = make_sug(user)
    r = other_auth_client.get(f"{URL}/{s.id}")
    assert r.status_code == 404 and r.json()["detail"] == "Nie znaleziono sugestii"
    assert other_auth_client.get(URL).json() == {"items": [], "total": 0}
    assert auth_client.get(f"{URL}/9999").status_code == 404


def test_legacy_surplus_suggestion_in_new_shape(auth_client, user, make_sug):
    # as left by migration 0007: report converted from summary/rationale/risks
    s = make_sug(
        user,
        type="surplus",
        month="2025-03",
        summary="Odłóż nadwyżkę.",
        rationale=[{"claim": "Nadwyżka jest dodatnia", "refers_to": "budget", "value": "3765.44"}],
        report={
            "headline": "Odłóż nadwyżkę.",
            "facts": [],
            "tables": [],
            "findings": [
                {
                    "title": "Nadwyżka jest dodatnia",
                    "detail": "",
                    "refers_to": "budget",
                    "value": "3765.44",
                }
            ],
            "recommendations": [],
            "risks": ["Inflacja."],
            "sources": [],
            "disclaimer": "d",
        },
    )
    item = auth_client.get(f"{URL}/{s.id}").json()
    assert item["action"] == "surplus" and item["headline"] == "Odłóż nadwyżkę."
    assert item["report"]["findings"][0]["value"] == "3765.44"
    assert item["report"]["risks"] == ["Inflacja."]


def test_legacy_row_without_report_is_converted(auth_client, user, make_sug):
    s = make_sug(
        user,
        type="surplus",
        report={},
        rationale=[{"claim": "Nadwyżka", "refers_to": "budget", "value": "1.00"}],
        risks=["Ryzyko."],
        sources=[{"title": "NBP", "url": "https://nbp.pl"}],
    )
    item = auth_client.get(f"{URL}/{s.id}").json()
    assert item["report"]["findings"][0]["title"] == "Nadwyżka"
    assert item["report"]["sources"][0]["url"] == "https://nbp.pl"


def test_run_saves_suggestion_listed_in_history(auth_client, profile, use_llm):
    use_llm(FakeLLM([final()]))
    run = auth_client.post("/api/agent/actions/portfolio_review/run", json={"params": {}}).json()
    items = auth_client.get(URL).json()["items"]
    assert [i["id"] for i in items] == [run["suggestion_id"]]
    assert items[0]["run_id"] == run["run_id"] and items[0]["source"] == "ai"
