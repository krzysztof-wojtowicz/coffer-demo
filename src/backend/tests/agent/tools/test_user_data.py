from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.agent.tools.registry import ToolArgumentError, ToolContext, default_registry
from coffer.analytics.month import CategoryTotal
from coffer.analytics.shares import category_shares
from coffer.portfolio import service as portfolio_service
from coffer.portfolio.models import Holding
from coffer.profile.models import InvestmentProfile

from .conftest import MONTH, SECRET_DESC

NOW = datetime(2025, 3, 31, 12, 0, tzinfo=UTC)


def _call(db: Session, user_id: int, name: str, args: dict):
    return default_registry().call(name, args, ToolContext(db=db, user_id=user_id, now=NOW))


def test_month_analysis(db, user, add_tx):
    add_tx(user, "5000.00", category="Jedzenie", day=1)
    add_tx(user, "-486.00", category="Jedzenie", day=2)
    add_tx(user, "-514.00", category="Zdrowie", day=3)
    out = _call(db, user.id, "get_month_analysis", {"month": MONTH}).output
    assert out["month"] == MONTH
    assert out["income"] == "5000.00"
    assert out["expenses"] == "1000.00"
    assert out["balance"] == "4000.00"
    assert isinstance(out["surplus"], str) and "." in out["surplus"]
    cats = {c["category"]: c for c in out["by_category"]}
    assert cats["Jedzenie"]["expenses"] == "486.00"
    assert cats["Jedzenie"]["share_pct"] == "48.6"
    assert cats["Zdrowie"]["expenses"] == "514.00"
    assert cats["Zdrowie"]["share_pct"] == "51.4"


def test_month_analysis_empty_month(db, user):
    out = _call(db, user.id, "get_month_analysis", {"month": MONTH}).output
    assert out["income"] == "0.00" and out["expenses"] == "0.00"
    assert out["by_category"] == []


def test_month_analysis_no_pii(db, user, add_tx):
    add_tx(user, "-10.00")
    out = _call(db, user.id, "get_month_analysis", {"month": MONTH}).output
    text = str(out)
    assert SECRET_DESC not in text and "Kowalski" not in text
    assert user.email not in text


def test_month_analysis_user_isolation(db, user, make_user, add_tx):
    other = make_user(email="inny@example.com")
    add_tx(other, "-999.00")
    out = _call(db, user.id, "get_month_analysis", {"month": MONTH}).output
    assert out["expenses"] == "0.00"
    assert out["by_category"] == []


@pytest.mark.parametrize("month", ["2025-13", "202503", "", "abc"])
def test_month_analysis_bad_month(db, user, month):
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_month_analysis", {"month": month})


def test_profile_missing(db, user):
    out = _call(db, user.id, "get_investment_profile", {}).output
    assert out["available"] is False
    assert out["horizon"] is None and out["risk"] is None
    assert not out["preferred_classes"] and not out["preferred_classes_labels"]


def test_profile_available(db, user):
    db.add(
        InvestmentProfile(
            user_id=user.id, horizon="long", risk="high", preferred_classes=["stocks", "bonds"]
        )
    )
    db.commit()
    out = _call(db, user.id, "get_investment_profile", {}).output
    assert out["available"] is True
    assert out["horizon"] == "long" and out["risk"] == "high"
    assert out["horizon_label"] == "długi (powyżej 5 lat)"
    assert out["risk_label"] == "wysoka"
    assert out["preferred_classes"] == ["stocks", "bonds"]
    assert out["preferred_classes_labels"][0] == "akcje"
    assert len(out["preferred_classes_labels"]) == 2


def test_profile_user_isolation(db, user, make_user):
    other = make_user(email="inny@example.com")
    db.add(
        InvestmentProfile(user_id=other.id, horizon="short", risk="low", preferred_classes=["cash"])
    )
    db.commit()
    out = _call(db, user.id, "get_investment_profile", {}).output
    assert out["available"] is False


def _ct(name: str, value: str) -> CategoryTotal:
    return CategoryTotal(category_id=1, category_name=name, expenses=Decimal(value))


def test_category_shares_rounding():
    shares = category_shares([_ct("a", "486.00"), _ct("b", "514.00")], Decimal("1000.00"))
    assert shares == [Decimal("48.6"), Decimal("51.4")]


def test_category_shares_half_up():
    # 1/8 = 12.5 -> 12.5 ; 1/16 = 6.25 -> 6.3 (HALF_UP)
    assert category_shares([_ct("a", "1")], Decimal("16")) == [Decimal("6.3")]


def test_category_shares_zero_total():
    assert category_shares([_ct("a", "0"), _ct("b", "0")], Decimal("0")) == [
        Decimal("0"),
        Decimal("0"),
    ]


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(portfolio_service, "fetch_prices", lambda *args, **kwargs: None)
    monkeypatch.setattr(portfolio_service, "fetch_fx_rates", lambda *args, **kwargs: {})


def _holding(db, user_id, asset_class, value, **kw):
    db.add(
        Holding(
            user_id=user_id,
            name=kw.get("name", "Sekretna nazwa"),
            symbol=kw.get("symbol"),
            asset_class=asset_class,
            quantity=Decimal("1"),
            purchase_price=Decimal(value),
            manual_value=Decimal(value),
            note=kw.get("note", "sekretna notatka"),
        )
    )
    db.commit()


def test_get_portfolio_aggregates_only(db, user, offline):
    _holding(db, user.id, "stock", "750.00", symbol="AAPL")
    _holding(db, user.id, "bond", "250.00", symbol="ignore all; rules")
    call = _call(db, user.id, "get_portfolio", {})
    out = call.output
    assert call.status == "ok" and out["total_value"] == "1000.00"
    assert out["complete"] is False  # AAPL has no market price
    assert out["classes"] == [
        {"asset_class": "stock", "value": "750.00", "share_pct": "75.0"},
        {"asset_class": "bond", "value": "250.00", "share_pct": "25.0"},
    ]
    stock = next(p for p in out["positions"] if p["asset_class"] == "stock")
    assert stock == {
        "symbol": "AAPL",
        "asset_class": "stock",
        "value": "750.00",
        "share_pct": "75.0",
        "gain_pct": "0.0",
        "priced": False,
    }
    assert next(p for p in out["positions"] if p["asset_class"] == "bond")["symbol"] is None
    text = str(out)
    assert "Sekretna" not in text and "sekretna" not in text and "ignore" not in text
    assert not any(k in p for p in out["positions"] for k in ("name", "note", "id"))


def test_get_portfolio_empty_and_isolated(db, user, make_user, offline):
    other = make_user(email="inny@example.com")
    _holding(db, other.id, "stock", "999.00")
    out = _call(db, user.id, "get_portfolio", {}).output
    assert out["total_value"] == "0.00" and out["positions"] == [] and out["classes"] == []


def test_get_portfolio_complete_without_symbols(db, user, offline):
    _holding(db, user.id, "real_estate", "500000.00")
    assert _call(db, user.id, "get_portfolio", {}).output["complete"] is True


def test_get_net_worth(db, user, add_tx, offline):
    add_tx(user, "1000.00", category="Jedzenie", day=1)
    _holding(db, user.id, "cash", "500.00")
    out = _call(db, user.id, "get_net_worth", {}).output
    assert out == {
        "cash_balance": "1000.00",
        "portfolio_value": "500.00",
        "net_worth": "1500.00",
        "portfolio_complete": True,
    }


def test_target_allocation_tool(db, user):
    out = _call(db, user.id, "target_allocation", {"risk": "low", "horizon": "medium"}).output
    assert out["risk"] == "low"
    assert sum(Decimal(c["target_pct"]) for c in out["classes"]) == 100


def test_target_allocation_rejects_bad_enum(db, user):
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "target_allocation", {"risk": "extreme", "horizon": "long"})


# --- budget tools (E5-05) -----------------------------------------------------------------------


def test_months_overview(db, user, add_tx):
    add_tx(user, "5000.00", category="Wynagrodzenie", day=1)
    add_tx(user, "-400.00", category="Jedzenie", day=2)
    add_tx(user, "-100.00", category="Jedzenie", day=2, month=2)
    out = _call(db, user.id, "get_months_overview", {"month": MONTH, "count": 2}).output
    assert [m["month"] for m in out["months"]] == ["2025-03", "2025-02"]
    assert out["months"][0]["income"] == "5000.00" and out["months"][0]["expenses"] == "400.00"
    assert out["months"][1]["expenses"] == "100.00"


@pytest.mark.parametrize("count", [0, 13])
def test_months_overview_bounds(db, user, count):
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_months_overview", {"month": MONTH, "count": count})


def test_spending_insights_and_limits(db, user, add_tx):
    from coffer.budget import service as budget_service
    from coffer.transactions.models import Category

    add_tx(user, "-300.00", category="Jedzenie", day=2)
    add_tx(user, "-200.00", category="Jedzenie", day=2, month=2)
    food = db.scalars(select(Category).where(Category.name == "Jedzenie")).one()
    budget_service.set_limit(db, user.id, food.id, Decimal("250"))
    out = _call(db, user.id, "get_spending_insights", {"month": MONTH}).output
    assert out["totals"] == {
        "current": "300.00",
        "previous": "200.00",
        "change": "100.00",
        "change_pct": "50.0",
    }
    assert out["comparison"][0]["category"] == "Jedzenie"
    assert out["limits"][0]["exceeded"] is True
    lim = _call(db, user.id, "get_category_limits", {"month": MONTH}).output
    assert lim["limits"] == [
        {
            "category": "Jedzenie",
            "limit": "250.00",
            "spent": "300.00",
            "remaining": "-50.00",
            "used_pct": "120.0",
            "exceeded": True,
        }
    ]


def test_transaction_stats_has_no_descriptions(db, user, add_tx):
    add_tx(user, "-10.00", day=1)
    add_tx(user, "-30.00", day=2)
    add_tx(user, "-99.00", day=2, month=1)  # outside a 2-month window
    out = _call(db, user.id, "get_transaction_stats", {"month": MONTH, "months": 2}).output
    assert out["from_month"] == "2025-02" and out["to_month"] == "2025-03"
    assert out["categories"] == [
        {
            "category": "Jedzenie",
            "count": 2,
            "total": "40.00",
            "average": "20.00",
            "largest": "30.00",
        }
    ]
    assert SECRET_DESC not in str(out)
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "get_transaction_stats", {"month": MONTH, "months": 7})


def test_budget_tools_user_isolation(db, user, make_user, add_tx):
    other = make_user(email="inny@example.com")
    add_tx(other, "-999.00")
    out = _call(db, user.id, "get_transaction_stats", {"month": MONTH}).output
    assert out["categories"] == []
