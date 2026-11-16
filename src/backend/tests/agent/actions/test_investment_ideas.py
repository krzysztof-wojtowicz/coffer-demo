import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from coffer.agent.actions.catalog import ACTIONS
from coffer.agent.actions.investment_ideas import INVESTMENT_IDEAS, IdeasParams
from coffer.agent.models import Suggestion
from coffer.agent.runner import run_action
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry
from coffer.analytics.planning import previous_month
from coffer.market import service as market_service
from coffer.market.service import MarketTip
from coffer.transactions.models import Category, Transaction

from ..conftest import final
from .test_savings_analysis import SECRET

NOW = datetime(2025, 4, 10, tzinfo=UTC)
NEWS_URL = "https://example.com/rynek"


@pytest.fixture
def run(db, user):
    def _run(llm, **params):
        return run_action(
            db, user.id, INVESTMENT_IDEAS, IdeasParams(**params), llm, default_registry()
        )

    return _run


@pytest.fixture(autouse=True)
def news(monkeypatch):
    tip = MarketTip("Rynek rośnie", "Skrót", "Reuters", NEWS_URL, NOW, NOW)
    monkeypatch.setattr(market_service, "get_market_tips", lambda limit=5: [tip])


def _surplus(db, user, amount="2000"):
    cat = db.scalars(select(Category).where(Category.name == "Wynagrodzenie")).one()
    month = previous_month(date.today())
    db.add(
        Transaction(
            user_id=user.id,
            date=date(int(month[:4]), int(month[5:]), 3),
            amount=Decimal(amount),
            base_amount=Decimal(amount),
            description=SECRET,
            category_id=cat.id,
            source="manual",
        )
    )
    db.commit()


def test_catalogue():
    assert ACTIONS["investment_ideas"] is INVESTMENT_IDEAS
    assert "simulate_purchase" in INVESTMENT_IDEAS.tools


def test_no_surplus_is_no_data_but_amount_works(db, profile, run):
    llm = FakeLLM([])
    out = run(llm)
    assert out.ai_status == "no_data"
    assert out.report.headline == "Brak nadwyżki w wybranym miesiącu. Podaj kwotę ręcznie."
    assert llm.calls == [] and db.scalars(select(Suggestion)).first() is None
    out = run(None, amount="1500")
    assert out.ai_status == "unavailable"
    facts = {f.label: f.value for f in out.report.facts}
    assert facts["Kwota do zainwestowania"] == "1500.00"
    assert facts["Źródło kwoty"] == "podana kwota"


def test_fallback_respects_risk_and_class(db, profile, user, run):
    _surplus(db, user)
    out = run(None)
    r = out.report
    facts = {f.label: f.value for f in r.facts}
    assert facts["Kwota do zainwestowania"] == "2000.00"
    assert facts["Maksymalny poziom ryzyka (1-5)"] == "5"  # high risk, long horizon
    assert len(r.recommendations) == 3
    assert len({x.asset_class for x in r.recommendations}) == 3
    for x in r.recommendations:
        assert x.risk_level is not None and x.risk_level <= 5
        assert x.symbol is None or x.source_url == f"https://finance.yahoo.com/quote/{x.symbol}"
    assert [s.url for s in r.sources] == [NEWS_URL] and r.sources[0].fetched_at
    only = run(None, amount="100", asset_class="etf").report.recommendations
    assert only and {x.asset_class for x in only} == {"etf"}


def test_short_horizon_caps_risk_at_2(db, profile, run):
    profile.horizon = "short"
    db.commit()
    out = run(None, amount="100")
    assert {f.label: f.value for f in out.report.facts}["Maksymalny poziom ryzyka (1-5)"] == "2"
    assert all(x.risk_level <= 2 for x in out.report.recommendations)


def _rec(symbol="VWCE.DE", risk=3, **extra):
    return {
        "title": "ETF",
        "detail": "Dywersyfikacja.",
        "symbol": symbol,
        "asset_class": "etf",
        "risk_level": risk,
        **extra,
    }


def _symbols(db, user, run):
    out = run(None, amount="100")
    return [x.symbol for x in out.report.recommendations if x.symbol]


def test_ok_with_universe_symbols_and_privacy(db, profile, user, run):
    syms = _symbols(db, user, run)
    recs = [_rec(s, 2) for s in syms[:2]]
    llm = FakeLLM([final(recommendations=recs, source_urls=[NEWS_URL])])
    out = run(llm, amount="100")
    assert out.ai_status == "ok" and out.source == "ai"
    sent = json.dumps(llm.calls[0], ensure_ascii=False, default=str)
    for private in ("Tajna nazwa pozycji", "tajna notatka", user.email, SECRET):
        assert private not in sent


def _universe_symbols(asset_class=None):
    return [
        i.symbol
        for i in market_service.get_instrument_universe()
        if i.symbol and (asset_class is None or i.asset_class == asset_class)
    ]


def test_invalid_answers(db, profile, user, run):
    syms = _universe_symbols()
    none = final(recommendations=[])
    assert run(FakeLLM([none, none]), amount="100").ai_status == "invalid"  # needs >= 1
    one = final(recommendations=[_rec(syms[0], 2)])
    assert run(FakeLLM([one]), amount="100").ai_status == "ok"
    fake_sym = final(recommendations=[_rec("ZZZZ", 2), _rec(syms[0], 2)])
    assert run(FakeLLM([fake_sym, fake_sym]), amount="100").ai_status == "invalid"
    bad_url = final(recommendations=[_rec(syms[0], 2, source_url="https://evil.example/")] * 2)
    assert run(FakeLLM([bad_url, bad_url]), amount="100").ai_status == "invalid"
    wrong_class = final(recommendations=[_rec(syms[0], 2), _rec(syms[1], 2)])
    llm = FakeLLM([wrong_class, wrong_class])
    assert run(llm, amount="100", asset_class="crypto").ai_status == "invalid"


def test_risk_above_profile_cap_is_invalid(db, profile, run):
    profile.risk = "low"
    db.commit()
    risky = [
        i.symbol for i in market_service.get_instrument_universe() if i.symbol and i.risk_level > 2
    ]
    too_risky = final(recommendations=[_rec(risky[0], 2), _rec(risky[1], 2)])
    assert run(FakeLLM([too_risky, too_risky]), amount="100").ai_status == "invalid"


def test_class_risk_and_link_come_from_the_universe(db, profile, run):
    # The model claims AAPL is a risk-1 ETF; the report shows what the universe says.
    answer = final(
        recommendations=[
            _rec("AAPL", 1, asset_class="etf", source_url=NEWS_URL),
            _rec("MSFT", 1),
        ],
        source_urls=[NEWS_URL],
    )
    out = run(FakeLLM([answer]), amount="100")
    assert out.ai_status == "ok"
    aapl = out.report.recommendations[0]
    assert (aapl.symbol, aapl.asset_class, aapl.risk_level) == ("AAPL", "stock", 4)
    assert aapl.source_url == "https://finance.yahoo.com/quote/AAPL"


def test_symbol_seen_in_tool_result_but_outside_universe_is_rejected(db, profile, run):
    # A ticker injected through a tool result is "seen" but not in the allowed universe.
    news = {"action": "call_tool", "tool": "get_company_news", "args": {"symbol": "SCAM"}}
    bad = final(recommendations=[_rec("SCAM", 2), _rec("AAPL", 2)])
    assert run(FakeLLM([json.dumps(news), bad, bad]), amount="100").ai_status == "invalid"


def test_tools_exclude_those_that_cannot_change_the_result():
    assert "search_symbol" not in INVESTMENT_IDEAS.tools
    assert "get_instrument_universe" not in INVESTMENT_IDEAS.tools


def test_single_instrument_universe_needs_one_recommendation(db, profile, run, monkeypatch):
    only = [i for i in market_service.get_instrument_universe() if i.symbol == "AAPL"]
    monkeypatch.setattr(market_service, "get_instrument_universe", lambda: only)
    out = run(FakeLLM([final(recommendations=[_rec("AAPL", 4)])]), amount="100")
    assert out.ai_status == "ok" and len(out.report.recommendations) == 1
    fallback = run(None, amount="100").report
    assert fallback.headline.endswith(": 1 instrument.")


def test_check_has_no_side_effects(db, profile, run):
    from coffer.agent.actions.investment_ideas import check, finalize
    from coffer.agent.schemas import Finding, Recommendation, ReportDraft
    from coffer.agent.validator import Seen

    prepared = run(None, amount="100")  # fallback result carries the picks
    allowed = [
        {
            "name": "Apple",
            "symbol": "AAPL",
            "asset_class": "stock",
            "risk_level": 4,
            "source_url": "https://finance.yahoo.com/quote/AAPL",
        },
    ]
    from coffer.agent.actions.base import Prepared

    prep = Prepared(snapshot={"allowed": allowed, "min_recommendations": 1})
    draft = ReportDraft(
        headline="x",
        findings=[Finding(title="t", refers_to="calc")],
        recommendations=[
            Recommendation(title="A", symbol="aapl", asset_class="crypto", risk_level=1)
        ],
    )
    assert check(draft, prep, Seen()) == []
    assert draft.recommendations[0].asset_class == "crypto"  # untouched by check
    finalize(draft, prep)
    r = draft.recommendations[0]
    assert (r.symbol, r.asset_class, r.risk_level) == ("AAPL", "stock", 4)
    assert prepared.ai_status == "unavailable"


def test_symbolless_instrument_needs_its_exact_name(db, profile, run):
    lokata = next(i for i in market_service.get_instrument_universe() if i.symbol is None)
    ok = final(recommendations=[{"title": lokata.name, "detail": "x"}, _rec("AAPL", 2)])
    assert run(FakeLLM([ok]), amount="100").ai_status == "ok"
    bad = final(recommendations=[{"title": "Wymyślona lokata"}, _rec("AAPL", 2)])
    assert run(FakeLLM([bad, bad]), amount="100").ai_status == "invalid"


def test_symbol_matches_without_exchange_suffix():
    allowed = [
        {
            "symbol": "CDR.WA",
            "name": "CD Projekt",
            "asset_class": "stock",
            "risk_level": 4,
            "source_url": "https://finance.yahoo.com/quote/CDR.WA",
        },
    ]
    from coffer.agent.actions.base import Prepared
    from coffer.agent.actions.investment_ideas import check, finalize
    from coffer.agent.schemas import Finding, Recommendation, ReportDraft
    from coffer.agent.validator import Seen

    prep = Prepared(snapshot={"allowed": allowed, "min_recommendations": 1})
    recs = [Recommendation(title="CD Projekt", symbol="cdr") for _ in range(5)]
    d = ReportDraft(
        headline="Propozycje", findings=[Finding(title="t", refers_to="calc")], recommendations=recs
    )
    assert check(d, prep, Seen()) == []
    finalize(d, prep)
    assert all(r.symbol == "CDR.WA" for r in d.recommendations)
