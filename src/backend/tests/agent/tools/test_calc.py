from datetime import UTC, datetime
from decimal import Decimal

import pytest

from coffer.agent.tools.registry import ToolArgumentError, ToolContext, default_registry
from coffer.budget import service as budget_service
from coffer.transactions.models import Category

NOW = datetime(2025, 4, 10, 12, 0, tzinfo=UTC)


def _call(db, user_id, name, args):
    return default_registry().call(name, args, ToolContext(db=db, user_id=user_id, now=NOW))


def test_simulate_purchase_on_user_portfolio(db, portfolio):
    out = _call(
        db, portfolio.id, "simulate_purchase", {"asset_class": "etf", "amount": "10000"}
    ).output
    assert out["total_before"] == "10000.00" and out["total_after"] == "20000.00"
    assert out["new_class"] is True
    after = {s["asset_class"]: s["share_pct"] for s in out["after"]}
    assert after == {"etf": "50.0", "stock": "25.0", "bond": "15.0", "cash": "10.0"}


def test_simulate_purchase_empty_portfolio_and_isolation(db, user, portfolio, make_user):
    other = make_user(email="inny@example.com")
    out = _call(db, other.id, "simulate_purchase", {"asset_class": "bond", "amount": "500"}).output
    assert out["before"] == [] and out["after"][0]["share_pct"] == "100.0"


@pytest.mark.parametrize(
    "args",
    [
        {"asset_class": "memecoin", "amount": "10"},
        {"asset_class": "etf", "amount": "0"},
        {"asset_class": "etf", "amount": "-1"},
    ],
)
def test_simulate_purchase_bad_args(db, user, args):
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "simulate_purchase", args)


def test_compound_interest(db, user):
    out = _call(
        db,
        user.id,
        "compound_interest",
        {"principal": "0", "monthly": "100", "annual_rate_pct": "12", "years": 1},
    ).output
    assert out["final_value"] == "1268.25" and out["contributed"] == "1200.00"
    assert out["interest"] == "68.25" and out["yearly"][0]["year"] == 1


@pytest.mark.parametrize(
    "patch", [{"annual_rate_pct": "31"}, {"years": 0}, {"years": 51}, {"monthly": "-1"}]
)
def test_compound_interest_bounds(db, user, patch):
    args = {"principal": "0", "monthly": "100", "annual_rate_pct": "3", "years": 5, **patch}
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "compound_interest", args)


def test_savings_goal_plan(db, user):
    out = _call(
        db, user.id, "savings_goal_plan", {"target": "6000", "current": "0", "months": 12}
    ).output
    assert out["monthly_amount"] == "500.00"
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "savings_goal_plan", {"target": "6000", "months": 0})


def test_propose_budget(db, user, add_tx):
    add_tx(user, "5000.00", category="Wynagrodzenie", day=1, month=3)
    add_tx(user, "-200.00", category="Jedzenie", day=2, month=2)
    add_tx(user, "-400.00", category="Jedzenie", day=2, month=3)
    add_tx(user, "-50.00", category="Przelewy własne", day=3, month=3)  # not a budget category
    food = db.query(Category).filter(Category.name == "Jedzenie").one()
    budget_service.set_limit(db, user.id, food.id, Decimal("350"))
    out = _call(
        db, user.id, "propose_budget", {"month": "2025-03", "months_back": 2, "cut_pct": "10"}
    ).output
    assert out["from_month"] == "2025-02" and out["to_month"] == "2025-03"
    assert out["average_income"] == "2500.00"
    assert out["proposed_limits"] == [
        {
            "category": "Jedzenie",
            "average": "300.00",
            "proposed_limit": "270.00",
            "current_limit": "350.00",
        }
    ]
    with pytest.raises(ToolArgumentError):
        _call(db, user.id, "propose_budget", {"month": "2025-03", "cut_pct": "60"})
