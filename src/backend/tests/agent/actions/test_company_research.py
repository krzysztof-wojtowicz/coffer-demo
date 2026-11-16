import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from coffer.agent.actions.catalog import ACTIONS
from coffer.agent.actions.company_research import COMPANY_RESEARCH, CompanyParams
from coffer.agent.models import Suggestion
from coffer.agent.runner import run_action
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry
from coffer.market import service as market_service
from coffer.market.service import CompanyProfile, MarketTip, PriceHistory, Quote, SymbolMatch

from ..conftest import final
from .test_savings_analysis import SECRET

NOW = datetime(2025, 4, 10, 12, tzinfo=UTC)
PROFILE_URL = "https://finance.yahoo.com/quote/PKO.WA/profile"
NEWS_URL = "https://example.com/pko-wyniki"


@pytest.fixture
def run(db, user):
    def _run(llm, query="PKO BP"):
        return run_action(
            db, user.id, COMPANY_RESEARCH, CompanyParams(query=query), llm, default_registry()
        )

    return _run


@pytest.fixture
def market(monkeypatch):
    from datetime import date

    monkeypatch.setattr(
        market_service,
        "search_symbols",
        lambda q, limit=5: (
            [
                SymbolMatch("PKO.WA", "PKO Bank Polski", "WSE", "EQUITY"),
                SymbolMatch("PKOBP.X", "Inny", None, "FUTURE"),
                SymbolMatch("PKN.WA", "Orlen", "WSE", "EQUITY"),
            ]
            if "PKO" in q.upper()
            else []
        ),
    )
    profile = CompanyProfile(
        "PKO.WA",
        "PKO Bank Polski",
        "Financial Services",
        "Banks",
        "PL",
        None,
        "Największy polski bank. " * 30,
        Decimal("70000000000"),
        Decimal("8.5"),
        Decimal("5.1"),
        "PLN",
        NOW,
        PROFILE_URL,
    )
    monkeypatch.setattr(market_service, "get_company_profile", lambda s: profile)
    monkeypatch.setattr(
        market_service,
        "get_quotes",
        lambda symbols, db=None: {
            "PKO.WA": Quote("PKO.WA", "PKO", Decimal("55.5"), "PLN", None, NOW)
        },
    )
    tip = MarketTip("Wyniki PKO BP", "Zysk wzrósł.", "Bankier", NEWS_URL, NOW, NOW)
    monkeypatch.setattr(market_service, "get_company_news", lambda s, limit=5: [tip])
    points = [(date(2024, 4, 10), Decimal("50")), (date(2025, 4, 10), Decimal("55.5"))]
    monkeypatch.setattr(
        market_service,
        "get_price_history",
        lambda s, p="1y": PriceHistory("PKO.WA", "PLN", points, NOW, "https://finance.yahoo.com/h"),
    )


def test_catalogue():
    assert ACTIONS["company_research"] is COMPANY_RESEARCH and len(ACTIONS) == 6
    assert COMPANY_RESEARCH.uses_user_data is False
    assert set(COMPANY_RESEARCH.tools) == {
        "get_company_news",
        "get_price_history",
        "get_wikipedia_summary",
        "get_quotes",
    }


@pytest.mark.parametrize("query", ["", "   ", "a;drop", "x" * 61, "<script>"])
def test_query_validation(query):
    with pytest.raises(ValueError):
        CompanyParams(query=query)


def test_no_match_is_no_data(db, user, run, market):
    llm = FakeLLM([])
    out = run(llm, query="zzz nic")
    assert out.ai_status == "no_data" and out.report.headline == (
        "Nie znaleziono spółki. Sprawdź nazwę lub ticker."
    )
    assert llm.calls == [] and db.scalars(select(Suggestion)).first() is None


def test_fallback_has_dated_sources(db, user, run, market):
    out = run(None)
    assert out.ai_status == "unavailable" and out.source == "rules"
    r = out.report
    facts = {f.label: f.value for f in r.facts}
    assert facts["Cena"] == "55.5 PLN" and facts["Zmiana 1 r. (%)"] == "11.00"
    assert facts["C/Z"] == "8.50" and facts["Sektor"] == "Financial Services"
    assert facts["Inne pasujące symbole"] == "PKN.WA"
    assert r.tables[0].id == "news" and r.tables[0].rows[0]["publisher"] == "Bankier"
    assert {s.url for s in r.sources} == {PROFILE_URL, NEWS_URL}
    assert all(s.fetched_at for s in r.sources)
    assert r.headline == "PKO Bank Polski (PKO.WA), sektor: Financial Services"
    assert len(r.findings[0].detail) <= 300 and r.findings[1].title == "Wyniki PKO BP"
    assert (
        r.disclaimer == "Informacje mają charakter poglądowy i nie są rekomendacją; sprawdź źródła."
    )


def test_ok_and_no_user_data_sent(db, portfolio, run, market):
    llm = FakeLLM(
        [
            final(
                headline="PKO Bank Polski kosztuje 55.5 PLN.",
                findings=[
                    {
                        "title": "Wyniki",
                        "detail": "Zysk wzrósł.",
                        "refers_to": "market",
                        "value": None,
                    }
                ],
                source_urls=[NEWS_URL],
            )
        ]
    )
    out = run(llm)
    assert out.ai_status == "ok" and out.source == "ai"
    assert any(s.url == NEWS_URL for s in out.report.sources)
    sent = json.dumps(llm.calls, ensure_ascii=False, default=str)
    private_values = ("Tajna nazwa pozycji", "tajna notatka", portfolio.email, SECRET, "10000")
    for private in private_values:
        assert private not in sent
    assert "PKO.WA" in sent


def test_invalid_when_url_or_symbol_outside_tools(db, user, run, market):
    bad_url = final(source_urls=["https://evil.example/x"])
    assert run(FakeLLM([bad_url, bad_url])).ai_status == "invalid"
    no_source = final(source_urls=[])
    assert run(FakeLLM([no_source, no_source])).ai_status == "invalid"
    user_data = final(
        findings=[{"title": "Budżet", "detail": "x", "refers_to": "budget", "value": None}],
        source_urls=[NEWS_URL],
    )
    assert run(FakeLLM([user_data, user_data])).ai_status == "invalid"


def test_profile_and_quote_down_is_no_data(db, user, run, market, monkeypatch):
    monkeypatch.setattr(market_service, "get_company_profile", lambda s: None)
    monkeypatch.setattr(market_service, "get_quotes", lambda symbols, db=None: {})
    assert run(None).ai_status == "no_data"
