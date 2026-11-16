import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from coffer.agent.actions.catalog import ACTIONS
from coffer.agent.actions.purchase_impact import PURCHASE_IMPACT, PurchaseParams
from coffer.agent.models import Suggestion
from coffer.agent.runner import run_action
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry
from coffer.analytics.planning import previous_month
from coffer.analytics.simulate import ClassValue, simulate_purchase
from coffer.market import service as market_service
from coffer.market.service import MarketDataUnavailable, Quote
from coffer.transactions.models import Category, Transaction

from ..conftest import final
from .test_savings_analysis import SECRET

NOW = datetime(2025, 4, 10, tzinfo=UTC)


@pytest.fixture
def run(db, user):
    def _run(llm, **params):
        return run_action(
            db, user.id, PURCHASE_IMPACT, PurchaseParams(**params), llm, default_registry()
        )

    return _run


@pytest.fixture
def market(monkeypatch):
    """Quotes: AAPL 100 USD; FX USD/PLN 4."""
    quotes = {"AAPL": Quote("AAPL", "Apple Inc.", Decimal("100"), "USD", None, NOW)}
    monkeypatch.setattr(
        market_service,
        "get_quotes",
        lambda symbols, db=None: {s: quotes[s] for s in symbols if s in quotes},
    )
    monkeypatch.setattr(
        market_service,
        "get_fx_quote",
        lambda a, b, db=None: (Decimal("1") if a == b else Decimal("4"), NOW),
    )


def _surplus(db, user, amount="3000"):
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
    assert ACTIONS["purchase_impact"] is PURCHASE_IMPACT
    assert len(ACTIONS) >= 4


@pytest.mark.parametrize(
    "params",
    [
        {"asset_class": "etf"},
        {"asset_class": "etf", "amount": "100", "quantity": "2"},
        {"asset_class": "etf", "quantity": "2"},
        {"asset_class": "etf", "amount": "100", "price": "5"},
        {"asset_class": "bitcoin", "amount": "100"},
        {"asset_class": "etf", "amount": "100", "currency": "JPY"},
        {"asset_class": "etf", "amount": "-1"},
        {"asset_class": "etf", "amount": "100", "symbol": "A B;"},
    ],
)
def test_params_invalid(params):
    with pytest.raises(ValueError):
        PurchaseParams(**params)


def test_unknown_price_is_no_data(db, portfolio, run, market):
    llm = FakeLLM([])
    out = run(llm, asset_class="stock", symbol="nope", quantity="3")
    assert out.ai_status == "no_data" and out.source == "none"
    assert out.report.headline == "Nie znamy ceny NOPE. Podaj cenę ręcznie."
    assert llm.calls == [] and db.scalars(select(Suggestion)).first() is None


def test_quotes_outage_is_no_data(db, portfolio, run, monkeypatch):
    def boom(symbols, db=None):
        raise MarketDataUnavailable

    monkeypatch.setattr(market_service, "get_quotes", boom)
    out = run(None, asset_class="stock", symbol="AAPL", quantity="3")
    assert out.ai_status == "no_data" and "Podaj cenę ręcznie" in out.report.headline


def test_unknown_fx_is_no_data(db, portfolio, run, monkeypatch):
    monkeypatch.setattr(market_service, "get_fx_quote", lambda a, b, db=None: None)
    out = run(None, asset_class="etf", amount="100", currency="EUR")
    assert out.ai_status == "no_data" and "EUR/PLN" in out.report.headline


def test_fallback_with_quote_and_fx(db, profile, user, run, market):
    _surplus(db, user)
    out = run(None, asset_class="stock", symbol="aapl", quantity="5")
    assert out.ai_status == "unavailable" and out.source == "rules"
    r = out.report
    facts = {f.label: f.value for f in r.facts}
    assert facts["Kwota zakupu (PLN)"] == "2000.00"  # 5 * 100 USD * 4
    assert facts["Kwota w granicach nadwyżki"] == "tak"
    assert facts["Wartość portfela po"] == "12000.00"
    # the table equals analytics, to the grosz
    impact = simulate_purchase(
        [
            ClassValue("stock", Decimal("5000")),
            ClassValue("bond", Decimal("3000")),
            ClassValue("cash", Decimal("2000")),
        ],
        "stock",
        Decimal("2000"),
    )
    rows = {row["asset_class"]: row for row in r.tables[0].rows}
    assert r.tables[0].id == "allocation_change"
    for s in impact.after:
        label = {"stock": "akcje", "bond": "obligacje", "cash": "gotówka"}[s.asset_class]
        assert rows[label]["after"] == f"{s.share_pct:.1f}"
    assert rows["akcje"] == {
        "asset_class": "akcje",
        "before": "50.0",
        "after": "58.3",
        "change": "8.3",
    }
    assert any("Wpływ na alokację" == f.title for f in r.findings)
    assert out.report.disclaimer == PURCHASE_IMPACT.disclaimer
    assert db.scalars(select(Suggestion)).one().profile_snapshot["risk"] == "high"


def test_manual_price_wins_and_no_profile_asks(db, portfolio, run, market):
    out = run(None, asset_class="etf", symbol="AAPL", quantity="10", price="50", currency="PLN")
    facts = {f.label: f.value for f in out.report.facts}
    assert facts["Kwota zakupu (PLN)"] == "500.00"
    assert facts["Kwota w granicach nadwyżki"] == "nie"  # no income last month
    titles = [x.title for x in out.report.recommendations]
    assert "Uzupełnij profil inwestycyjny" in titles


def test_concentration_warning(db, profile, user, run, market):
    out = run(None, asset_class="stock", amount="20000")
    assert any("koncentracji" in x for x in out.report.risks)


def test_empty_portfolio_new_class_100(db, user, run, market):
    out = run(None, asset_class="bond", amount="1000")
    assert out.ai_status == "unavailable"
    assert out.report.tables[0].rows == [
        {"asset_class": "obligacje", "before": "0.0", "after": "100.0", "change": "100.0"}
    ]
    assert any(f.title == "Nowa klasa aktywów" for f in out.report.findings)


def test_ok_privacy_and_validation(db, profile, user, run, market):
    llm = FakeLLM(
        [
            final(
                headline="Zakup 1000.00 PLN zmienia udział akcji.",
                findings=[
                    {
                        "title": "Akcje",
                        "detail": "Udział po zakupie to 54.5%.",
                        "refers_to": "portfolio",
                        "value": "54.5",
                    }
                ],
            )
        ]
    )
    out = run(llm, asset_class="stock", amount="1000")
    assert out.ai_status == "ok" and out.source == "ai"
    sent = json.dumps(llm.calls[0], ensure_ascii=False, default=str)
    for secret in ("Tajna nazwa pozycji", "tajna notatka", user.email, SECRET):
        assert secret not in sent
    bad = final(headline="Zakup da 999999.99 PLN.")
    assert run(FakeLLM([bad, bad]), asset_class="stock", amount="1000").ai_status == "invalid"
    unknown_cls = final(recommendations=[{"title": "Kup", "asset_class": "memecoins"}])
    assert (
        run(FakeLLM([unknown_cls, unknown_cls]), asset_class="stock", amount="1000").ai_status
        == "invalid"
    )


def test_failing_tool_in_prepare_is_no_data_not_500(db, user, run, market, monkeypatch):
    from coffer.agent.models import AgentRun
    from coffer.agent.tools import calc

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(calc.portfolio_service, "summary", boom)
    out = run(None, asset_class="etf", amount="100")
    assert out.ai_status == "no_data" and out.source == "none"
    assert out.report.headline.startswith("Narzędzie nie zadziałało")
    assert db.scalars(select(AgentRun)).one().status == "no_data"
    assert db.scalars(select(Suggestion)).first() is None
