import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from coffer.agent.actions.catalog import ACTIONS
from coffer.agent.actions.savings_analysis import SAVINGS_ANALYSIS, SavingsParams
from coffer.agent.models import Suggestion
from coffer.agent.runner import run_action
from coffer.agent.testing import FakeLLM
from coffer.agent.tools.registry import default_registry
from coffer.budget import service as budget_service
from coffer.transactions.models import Category, Transaction

from ..conftest import final

SECRET = "Sekretny opis Jan Kowalski"
MONTH = "2025-03"


def add_tx(db, user, amount, category="Jedzenie", year=2025, month=3, day=10):
    cat = db.scalars(select(Category).where(Category.name == category)).one()
    db.add(
        Transaction(
            user_id=user.id,
            date=date(year, month, day),
            amount=Decimal(amount),
            base_amount=Decimal(amount),
            description=SECRET,
            category_id=cat.id,
            source="manual",
        )
    )
    db.commit()
    return cat


@pytest.fixture
def run(db, user):
    def _run(llm, **params):
        return run_action(
            db,
            user.id,
            SAVINGS_ANALYSIS,
            SavingsParams(month=MONTH, **params),
            llm,
            default_registry(),
        )

    return _run


@pytest.fixture
def budget(db, user):
    add_tx(db, user, "5000", "Wynagrodzenie", month=3, day=1)
    for m, amount in ((12, "-100"), (1, "-100"), (2, "-100")):
        add_tx(db, user, amount, "Jedzenie", year=2024 if m == 12 else 2025, month=m)
    food = add_tx(db, user, "-400", "Jedzenie", month=3)
    add_tx(db, user, "-90", "Rozrywka", month=3)
    add_tx(db, user, "-60", "Rozrywka", month=2)
    budget_service.set_limit(db, user.id, food.id, Decimal("350"))
    return user


def test_catalogue():
    assert ACTIONS["savings_analysis"] is SAVINGS_ANALYSIS
    assert "get_spending_insights" in SAVINGS_ANALYSIS.tools


def test_catalog_is_consistent():
    from dataclasses import replace

    from coffer.agent.actions import catalog

    assert catalog.validate_catalog(default_registry()) == []
    bad = replace(SAVINGS_ANALYSIS, id="bad", uses_user_data=False)
    catalog.ACTIONS["bad"] = bad
    try:
        errors = catalog.validate_catalog(default_registry())
    finally:
        del catalog.ACTIONS["bad"]
    assert any("get_month_analysis" in e and "uses_user_data" in e for e in errors)


def test_params_bounds():
    with pytest.raises(ValueError):
        SavingsParams(months_back=7)
    with pytest.raises(ValueError):
        SavingsParams(month="2025-13")


def test_no_data(db, user, run):
    llm = FakeLLM([])
    out = run(llm)
    assert out.ai_status == "no_data" and out.source == "none"
    assert out.report.headline == "Brak transakcji w wybranym miesiącu."
    assert llm.calls == [] and db.scalars(select(Suggestion)).first() is None


def test_fallback_tables_and_recommendations(db, budget, run):
    out = run(None)
    assert out.ai_status == "unavailable" and out.source == "rules"
    r = out.report
    facts = {f.label: f.value for f in r.facts}
    assert facts["Wydatki"] == "490.00" and facts["Nadwyżka"] == "4510.00"
    assert facts["Zmiana wydatków vs poprzedni miesiąc"] == "330.00"  # 490 - 160
    assert facts["Liczba przekroczonych limitów"] == "1"
    tables = {t.id: t for t in r.tables}
    assert set(tables) == {"comparison", "top_growth", "limits"}
    assert tables["comparison"].rows[0]["category"] == "Jedzenie"
    assert tables["comparison"].rows[0]["change"] == "300.00"
    assert tables["limits"].rows == [
        {
            "category": "Jedzenie",
            "limit": "350.00",
            "spent": "400.00",
            "remaining": "-50.00",
            "used_pct": "114.3",
            "status": "przekroczony",
        }
    ]
    growth = {row["category"]: row for row in tables["top_growth"].rows}
    assert growth["Jedzenie"]["increase"] == "300.00"
    assert r.findings and r.recommendations
    titles = [x.title for x in r.recommendations]
    assert "Zmniejsz wydatki: Jedzenie" in titles
    detail = next(x.detail for x in r.recommendations if x.title.startswith("Ogranicz"))
    assert "40.00 zł/mies., 480.00 zł/rok" in detail  # 10% of 400
    assert r.disclaimer == SAVINGS_ANALYSIS.disclaimer
    assert db.scalars(select(Suggestion)).one().source == "rules"


def test_ok_and_privacy(db, budget, run):
    llm = FakeLLM(
        [
            final(
                headline="Wydatki wynoszą 490.00 PLN.",
                findings=[
                    {
                        "title": "Jedzenie",
                        "detail": "Wydano 400.00 PLN.",
                        "refers_to": "budget",
                        "value": "400.00",
                    }
                ],
            )
        ]
    )
    out = run(llm)
    assert out.ai_status == "ok" and out.source == "ai"
    assert [t.id for t in out.report.tables] == ["comparison", "top_growth", "limits"]
    sent = json.dumps(llm.calls[0], ensure_ascii=False, default=str)
    assert SECRET not in sent and "Jedzenie" in sent and budget.email not in sent


def test_invalid_number_falls_back(db, budget, run):
    bad = final(headline="Wydatki wynoszą 777777.77 PLN.")
    out = run(FakeLLM([bad, bad]))
    assert out.ai_status == "invalid" and out.source == "rules" and out.report.findings
