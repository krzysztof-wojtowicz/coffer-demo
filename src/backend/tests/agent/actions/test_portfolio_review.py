import json

import pytest
from sqlalchemy import select

from coffer.agent.actions.catalog import ACTIONS, get_action
from coffer.agent.actions.portfolio_review import PORTFOLIO_REVIEW, NoParams
from coffer.agent.models import AgentRun, Suggestion
from coffer.agent.runner import run_action
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry

from ..conftest import final


@pytest.fixture
def run(db, user):
    def _run(llm):
        return run_action(db, user.id, PORTFOLIO_REVIEW, NoParams(), llm, default_registry())

    return _run


def test_catalogue():
    assert get_action("portfolio_review") is PORTFOLIO_REVIEW is ACTIONS["portfolio_review"]
    assert get_action("surplus") is None
    assert PORTFOLIO_REVIEW.tools == (
        "get_portfolio",
        "get_investment_profile",
        "get_net_worth",
        "target_allocation",
        "get_price_history",
    )
    assert len(PORTFOLIO_REVIEW.id) <= 30


def test_empty_portfolio_is_no_data(db, user, run):
    llm = FakeLLM([])
    out = run(llm)
    assert out.ai_status == "no_data" and out.source == "none"
    assert out.report.headline == "Portfel jest pusty. Dodaj pozycje, aby uzyskać analizę."
    assert llm.calls == [] and db.scalars(select(Suggestion)).first() is None


def test_fallback_with_profile(db, profile, run):
    out = run(None)
    assert out.ai_status == "unavailable" and out.source == "rules"
    r = out.report
    facts = {f.label: (f.value, f.kind) for f in r.facts}
    assert facts["Wartość portfela"] == ("10000.00", "money")
    assert facts["Liczba pozycji"] == ("3", "number")
    assert facts["Największa pozycja"] == ("50.0", "percent")
    assert facts["Udział gotówki w majątku"] == ("0.0", "percent")
    table = r.tables[0]
    assert table.id == "allocation"
    rows = {row["asset_class"]: row for row in table.rows}
    assert rows["akcje"] == {
        "asset_class": "akcje",
        "current": "50.0",
        "target": "40.0",
        "gap": "-10.0",
    }
    assert rows["fundusze ETF"]["gap"] == "45.0"
    titles = [x.title for x in r.recommendations]
    assert "Zwiększ udział: fundusze ETF" in titles
    assert "Zmniejsz udział: obligacje" in titles
    assert "Uzupełnij profil inwestycyjny" not in titles
    assert any("koncentracja" in f.title for f in r.findings)
    assert any("niepełna" in x for x in r.risks)  # AAPL has no quote offline
    assert r.disclaimer == PORTFOLIO_REVIEW.disclaimer
    sug = db.scalars(select(Suggestion)).one()
    assert sug.profile_snapshot["risk"] == "high" and sug.source == "rules"
    assert sug.data_snapshot["total_value"] == "10000.00"


def test_fallback_without_profile_uses_default_and_asks_for_profile(db, portfolio, run):
    out = run(None)
    r = out.report
    assert any(f.refers_to == "profile" for f in r.findings)
    assert "Uzupełnij profil inwestycyjny" in [x.title for x in r.recommendations]
    # default medium/medium target: stock 20 -> the 50% stock holding is 30 p.p. over
    assert "Zmniejsz udział: akcje" in [x.title for x in r.recommendations]
    assert db.scalars(select(Suggestion)).one().profile_snapshot is None


def test_balanced_portfolio_has_no_rebalance(db, user, add_holding, run):
    spread = [("cash", "1500"), ("bond", "1500"), ("bond", "1500"), ("etf", "1500")]
    spread += [("etf", "1500"), ("stock", "1000"), ("stock", "1000")]
    for cls, value in spread:
        add_holding(user, cls, value)
    add_holding(user, "real_estate", "500")
    out = run(None)
    assert out.report.recommendations == [] or all(
        x.title == "Uzupełnij profil inwestycyjny" for x in out.report.recommendations
    )
    assert any("zbliżona do celu" in f.title for f in out.report.findings)
    assert not any("koncentracja" in f.title for f in out.report.findings)


def test_model_gets_only_aggregates(db, user, profile, run):
    llm = FakeLLM([final()])
    out = run(llm)
    assert out.ai_status == "ok"
    sent = json.dumps(llm.calls[0], ensure_ascii=False, default=str)
    for secret in ("Tajna nazwa pozycji", "tajna notatka", user.email):
        assert secret not in sent
    assert "AAPL" in sent
    assert llm.calls[0]["response_schema"]["properties"]["tool"]["enum"] == list(
        PORTFOLIO_REVIEW.tools
    )
    run_row = db.scalars(select(AgentRun)).one()
    assert "Tajna nazwa pozycji" not in json.dumps(run_row.steps, ensure_ascii=False)
    assert "tajna notatka" not in json.dumps(run_row.messages, ensure_ascii=False)


def test_valid_model_answer_with_known_numbers(db, profile, run):
    answer = final(
        headline="Portfel wart 10000.00 PLN, największa pozycja to 50.0%.",
        recommendations=[{"title": "Dodaj ETF", "detail": "Cel to 45.0%.", "asset_class": "etf"}],
    )
    out = run(FakeLLM([answer]))
    assert out.ai_status == "ok" and out.source == "ai"
    assert out.report.recommendations[0].asset_class == "etf"
    assert [t.id for t in out.report.tables] == ["allocation"]  # tables stay deterministic


def test_model_can_call_whitelisted_tool(db, profile, run):
    llm = FakeLLM(
        [
            json.dumps(
                {
                    "action": "call_tool",
                    "tool": "target_allocation",
                    "args": {"risk": "low", "horizon": "short"},
                }
            ),
            final(),
        ]
    )
    assert run(llm).ai_status == "ok"
    steps = db.scalars(select(AgentRun)).one().steps
    assert [s["name"] for s in steps if s["kind"] == "tool" and s["origin"] == "model"] == [
        "target_allocation"
    ]


def test_validator_rejects_number_outside_data(db, profile, run):
    bad = final(headline="Portfel wart 777777.77 PLN.")
    out = run(FakeLLM([bad, bad]))
    assert out.ai_status == "invalid" and out.source == "rules"
    assert any("777777.77" in e for e in db.scalars(select(AgentRun)).one().validation_errors)


def test_validator_rejects_url_outside_tool_results(db, profile, run):
    bad = final(source_urls=["https://evil.example/phish"])
    assert run(FakeLLM([bad, bad])).ai_status == "invalid"


def test_unknown_asset_class_rejected(db, profile, run):
    bad = final(recommendations=[{"title": "Kup", "asset_class": "memecoins"}])
    assert run(FakeLLM([bad, bad])).ai_status == "invalid"


def test_params_must_be_empty():
    with pytest.raises(ValueError):
        NoParams.model_validate({"month": "2025-03"})
