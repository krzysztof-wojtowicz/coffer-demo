import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from coffer.agent.actions.budget_plan import BUDGET_PLAN, BudgetPlanParams
from coffer.agent.actions.catalog import ACTIONS
from coffer.agent.models import Suggestion
from coffer.agent.runner import run_action
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry
from coffer.analytics.planning import previous_month, shift_month
from coffer.budget import service as budget_service
from coffer.transactions.models import Category, Transaction

from ..conftest import final
from .test_savings_analysis import SECRET


def _add(db, user, month: str, amount: str, category: str):
    cat = db.scalars(select(Category).where(Category.name == category)).one()
    year, mon = int(month[:4]), int(month[5:])
    db.add(
        Transaction(
            user_id=user.id,
            date=date(year, mon, 5),
            amount=Decimal(amount),
            base_amount=Decimal(amount),
            description=SECRET,
            category_id=cat.id,
            source="manual",
        )
    )
    db.commit()
    return cat


FOOD: dict[str, int] = {}


@pytest.fixture
def run(db, user):
    def _run(llm, **params):
        return run_action(
            db, user.id, BUDGET_PLAN, BudgetPlanParams(**params), llm, default_registry()
        )

    return _run


@pytest.fixture
def history(db, user):
    last = previous_month(date.today())
    months = [last, shift_month(last, -1)]
    food = None
    for month, food_amount in zip(months, ("-420", "-300"), strict=True):
        _add(db, user, month, "3000", "Wynagrodzenie")
        food = _add(db, user, month, food_amount, "Jedzenie")
    budget_service.set_limit(db, user.id, food.id, Decimal("500"))
    FOOD["id"] = food.id
    return user


def test_catalogue_and_params():
    assert ACTIONS["budget_plan"] is BUDGET_PLAN
    with pytest.raises(ValueError):
        BudgetPlanParams(savings_target=Decimal("1000"))  # goal needs the term as well
    with pytest.raises(ValueError):
        BudgetPlanParams(months_back=0)
    assert BudgetPlanParams(savings_target=Decimal("1000"), target_months=10).target_months == 10


def test_no_data(db, user, run):
    out = run(FakeLLM([]))
    assert out.ai_status == "no_data" and out.report.headline.startswith("Brak transakcji")
    assert db.scalars(select(Suggestion)).first() is None


def test_fallback_proposal_and_goal(db, history, run):
    out = run(None, months_back=2, savings_target="2400", target_months=12)
    assert out.ai_status == "unavailable" and out.source == "rules"
    r = out.report
    facts = {f.label: f.value for f in r.facts}
    assert facts["Średnie przychody"] == "3000.00"
    assert facts["Średnie wydatki"] == "360.00"
    assert facts["Średnia nadwyżka"] == "2640.00"
    assert facts["Wymagana kwota miesięczna"] == "200.00"
    example = next(v for k, v in facts.items() if k.startswith("Przykład"))
    assert example == "170393.91" or Decimal(example) > Decimal("2640") * 60
    (table,) = r.tables
    assert table.id == "proposed_limits"
    # avg 360; Jedzenie grows (420 > 360) -> 360 * 0.9 = 324 -> up to 330
    assert [r.pop("category_id") for r in table.rows] == [str(FOOD["id"])]
    assert "category_id" not in {c.key for c in table.columns}
    assert table.rows == [
        {
            "category": "Jedzenie",
            "average": "360.00",
            "proposed_limit": "330.00",
            "current_limit": "500.00",
        }
    ]
    assert any("osiągalny" in f.detail for f in r.findings)
    assert r.recommendations[0].title == "Ustaw limit: Jedzenie"


def test_ok_and_privacy(db, history, run):
    llm = FakeLLM(
        [
            final(
                headline="Średnia nadwyżka to 2640.00 PLN.",
                findings=[
                    {
                        "title": "Jedzenie",
                        "detail": "Limit 330.00 PLN.",
                        "refers_to": "budget",
                        "value": "330.00",
                    }
                ],
            )
        ]
    )
    out = run(llm, months_back=2)
    assert out.ai_status == "ok" and out.source == "ai"
    assert out.report.tables[0].id == "proposed_limits"
    sent = json.dumps(llm.calls[0], ensure_ascii=False, default=str)
    assert SECRET not in sent and history.email not in sent
    assert "category_id" not in sent


def test_unavailable_when_model_invalid(db, history, run):
    bad = final(headline="Zaoszczędzisz 123456.78 PLN.")
    out = run(FakeLLM([bad, bad]), months_back=2)
    assert out.ai_status == "invalid" and out.source == "rules" and out.report.findings
