from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from coffer.agent.tools.registry import ToolArgumentError, ToolContext, default_registry
from coffer.analytics.month import CategoryTotal
from coffer.analytics.shares import category_shares
from coffer.profile.models import InvestmentProfile

from .conftest import MONTH, SECRET_DESC


def _call(db: Session, user_id: int, name: str, args: dict):
    return default_registry().call(name, args, ToolContext(db=db, user_id=user_id))


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
