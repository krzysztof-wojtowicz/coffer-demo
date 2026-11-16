from datetime import UTC, datetime
from decimal import Decimal

import pytest

from coffer.agent.tools.registry import ToolArgumentError, ToolContext, default_registry
from coffer.market import service as market_service
from coffer.market.service import MarketDataUnavailable, Quote

NOW = datetime(2025, 4, 10, 12, 0, tzinfo=UTC)


def _call(db, user_id, name, args):
    return default_registry().call(name, args, ToolContext(db=db, user_id=user_id, now=NOW))


def _quote(symbol="AAPL", price="190.5", currency="USD"):
    return Quote(symbol, "Apple Inc.", Decimal(price), currency, Decimal("1.25"), NOW)


def test_quotes(db, user, monkeypatch):
    monkeypatch.setattr(market_service, "get_quotes", lambda symbols, db=None: {"AAPL": _quote()})
    call = _call(db, user.id, "get_quotes", {"symbols": ["aapl", "ZZZZ", "bad symbol!"]})
    assert call.status == "ok"
    out = call.output
    q = out["quotes"][0]
    assert q["symbol"] == "AAPL" and q["price"] == "190.5" and q["currency"] == "USD"
    assert q["source_url"] == "https://finance.yahoo.com/quote/AAPL"
    assert q["fetched_at"] == NOW.isoformat()  # the quote time, not "now"
    assert out["unknown"] == ["ZZZZ"]


def test_quotes_unavailable_is_polish_error(db, user, monkeypatch):
    def boom(symbols, db=None):
        raise MarketDataUnavailable

    monkeypatch.setattr(market_service, "get_quotes", boom)
    call = _call(db, user.id, "get_quotes", {"symbols": ["AAPL"]})
    assert call.status == "error" and call.output == {
        "error": "Dane rynkowe są chwilowo niedostępne"
    }


def test_quotes_only_invalid_symbols(db, user):
    call = _call(db, user.id, "get_quotes", {"symbols": ["a b", "x/y"]})
    assert call.status == "error"


def test_quotes_limits(db, user):
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_quotes", {"symbols": [f"S{i}" for i in range(11)]})
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_quotes", {"symbols": []})


def test_fx_rate(db, user, monkeypatch):
    monkeypatch.setattr(
        market_service, "get_fx_quote", lambda a, b, db=None: (Decimal("4.0123"), NOW)
    )
    out = _call(db, user.id, "get_fx_rate", {"from_ccy": "usd", "to_ccy": "PLN"}).output
    assert out["rate"] == "4.0123" and out["from_ccy"] == "USD"
    assert out["source_url"] == "https://finance.yahoo.com/quote/USDPLN=X"


def test_fx_rate_unknown(db, user, monkeypatch):
    monkeypatch.setattr(market_service, "get_fx_quote", lambda a, b, db=None: None)
    call = _call(db, user.id, "get_fx_rate", {"from_ccy": "USD", "to_ccy": "PLN"})
    assert call.status == "error" and "USD/PLN" in call.output["error"]
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_fx_rate", {"from_ccy": "US", "to_ccy": "PLN"})


def test_registry_has_e5_05_tools():
    names = set(default_registry().names())
    assert {
        "get_months_overview",
        "get_spending_insights",
        "get_transaction_stats",
        "get_category_limits",
        "simulate_purchase",
        "compound_interest",
        "savings_goal_plan",
        "propose_budget",
        "get_quotes",
        "get_fx_rate",
    } <= names


# --- E5-07 tools -----------------------------------------------------------------------------


def _history(n=100):
    from datetime import date, timedelta

    from coffer.market.service import PriceHistory

    points = [(date(2025, 1, 1) + timedelta(days=i), Decimal(100 + i)) for i in range(n)]
    return PriceHistory("AAPL", "USD", points, NOW, "https://finance.yahoo.com/quote/AAPL/history")


def test_price_history_downsampled_with_stats(db, user, monkeypatch):
    monkeypatch.setattr(market_service, "get_price_history", lambda s, p="1y": _history())
    out = _call(db, user.id, "get_price_history", {"symbol": "aapl", "period": "3mo"}).output
    assert len(out["points"]) == 30
    assert out["points"][0]["close"] == "100.00" and out["points"][-1]["close"] == "199.00"
    assert out["price_stats"]["return_pct"] == "99.00"
    assert out["source_url"].endswith("/AAPL/history") and out["fetched_at"]


def test_price_history_errors(db, user, monkeypatch):
    monkeypatch.setattr(market_service, "get_price_history", lambda s, p="1y": None)
    call = _call(db, user.id, "get_price_history", {"symbol": "AAPL"})
    assert call.status == "error" and call.output["error"] == "Dane rynkowe są chwilowo niedostępne"
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_price_history", {"symbol": "AAPL", "period": "10y"})
    assert _call(db, user.id, "get_price_history", {"symbol": "a b"}).status == "error"


def test_company_profile_truncates_summary(db, user, monkeypatch):
    from coffer.market.service import CompanyProfile

    profile = CompanyProfile(
        "AAPL",
        "Apple Inc.",
        "Technology",
        None,
        "US",
        None,
        "x" * 2000,
        Decimal("3000000000000"),
        Decimal("30.5"),
        Decimal("0.5"),
        "USD",
        NOW,
        "https://finance.yahoo.com/quote/AAPL/profile",
    )
    monkeypatch.setattr(market_service, "get_company_profile", lambda s: profile)
    out = _call(db, user.id, "get_company_profile", {"symbol": "AAPL"}).output
    assert len(out["summary"]) <= 600 and out["pe_ratio"] == "30.50"
    assert out["source_url"].endswith("/profile") and out["fetched_at"]
    monkeypatch.setattr(market_service, "get_company_profile", lambda s: None)
    assert _call(db, user.id, "get_company_profile", {"symbol": "AAPL"}).status == "error"


def _tip(title="Rynek rośnie"):
    from coffer.market.service import MarketTip

    return MarketTip(title, "Skrót", "Reuters", "https://example.com/a", NOW, NOW)


def test_news_tools(db, user, monkeypatch):
    monkeypatch.setattr(market_service, "get_company_news", lambda s, limit=5: [_tip()])
    out = _call(db, user.id, "get_company_news", {"symbol": "AAPL", "limit": 3}).output
    assert (
        out["news"][0]["url"] == "https://example.com/a"
        and out["news"][0]["publisher"] == "Reuters"
    )
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_company_news", {"symbol": "AAPL", "limit": 6})
    monkeypatch.setattr(market_service, "get_market_tips", lambda limit=5: [])
    assert _call(db, user.id, "get_market_news", {}).status == "error"
    monkeypatch.setattr(market_service, "get_market_tips", lambda limit=5: [_tip()])
    assert _call(db, user.id, "get_market_news", {"limit": 1}).output["news"][0]["title"]


def test_search_wiki_universe(db, user, monkeypatch):
    from coffer.market.service import EncyclopediaEntry, SymbolMatch

    monkeypatch.setattr(
        market_service,
        "search_symbols",
        lambda q, limit=5: [SymbolMatch("PKO.WA", "PKO BP", "WSE", "EQUITY")],
    )
    out = _call(db, user.id, "search_symbol", {"query": "pko"}).output
    assert out["matches"][0]["symbol"] == "PKO.WA"
    entry = EncyclopediaEntry("PKO BP", "Bank.", "https://pl.wikipedia.org/wiki/PKO", NOW)
    monkeypatch.setattr(market_service, "get_wikipedia_summary", lambda q, lang="pl": entry)
    wiki = _call(db, user.id, "get_wikipedia_summary", {"query": "PKO BP"}).output
    assert wiki["url"].startswith("https://pl.wikipedia.org")
    monkeypatch.setattr(market_service, "get_wikipedia_summary", lambda q, lang="pl": None)
    assert _call(db, user.id, "get_wikipedia_summary", {"query": "x"}).status == "error"
    uni = _call(db, user.id, "get_instrument_universe", {}).output["instruments"]
    assert any(i["symbol"] == "AAPL" and i["source_url"] for i in uni)
