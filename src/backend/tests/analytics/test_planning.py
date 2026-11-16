from datetime import date
from decimal import Decimal

import pytest

from coffer.analytics.month import CategoryTotal, MonthSummary
from coffer.analytics.planning import (
    average_by_category,
    average_totals,
    compound_growth,
    monthly_saving_for_goal,
    previous_month,
    propose_limits,
    shift_month,
)

D = Decimal


def test_compound_growth_zero_rate():
    r = compound_growth(D("1000"), D("100"), D("0"), 2)
    assert r.final_value == D("3400.00") and r.contributed == D("3400.00")
    assert r.interest == D("0.00")
    assert [(y.year, y.balance) for y in r.yearly] == [(1, D("2200.00")), (2, D("3400.00"))]


def test_compound_growth_monthly_compounding():
    # 12 payments of 100 at 12%/year = 1% per month: FV annuity = 100 * (1.01^12 - 1) / 0.01
    r = compound_growth(D("0"), D("100"), D("12"), 1)
    assert r.final_value == D("1268.25")
    assert r.contributed == D("1200.00") and r.interest == D("68.25")


def test_compound_growth_rejects_negative():
    with pytest.raises(ValueError):
        compound_growth(D("-1"), D("0"), D("1"), 1)


def test_goal_zero_rate_and_reached():
    assert monthly_saving_for_goal(D("1200"), D("0"), 12) == D("100.00")
    assert monthly_saving_for_goal(D("1000"), D("1000"), 6) == D("0.00")
    assert monthly_saving_for_goal(D("100"), D("500"), 6) == D("0.00")


def test_goal_with_interest_inverts_growth():
    pay = monthly_saving_for_goal(D("10000"), D("500"), 24, D("5"))
    final = compound_growth(D("500"), pay, D("5"), 2).final_value
    assert abs(final - D("10000")) < D("1")
    assert pay < monthly_saving_for_goal(D("10000"), D("500"), 24)


def test_goal_invalid_months():
    with pytest.raises(ValueError):
        monthly_saving_for_goal(D("100"), D("0"), 0)


def test_propose_limits_rounds_up_and_cuts_growth():
    averages = {1: ("Jedzenie", D("812.50")), 2: ("Transport", D("200.00")), 3: ("Inne", D("0.00"))}
    out = {p.category_name: p for p in propose_limits(averages, {1}, D("10"))}
    assert out["Jedzenie"].proposed == D("740.00")  # 731.25 -> up to 740
    assert out["Transport"].proposed == D("200.00")
    assert out["Inne"].proposed == D("0.00")
    assert out["Jedzenie"].average == D("812.50")
    assert [p.category_name for p in propose_limits(averages, set(), D("0"))][0] == "Jedzenie"


def test_propose_limits_bad_cut():
    with pytest.raises(ValueError):
        propose_limits({}, set(), D("101"))


def _month(name: str, income: str, cats: list[tuple[int, str, str, bool]]) -> MonthSummary:
    by = [CategoryTotal(i, n, D(v), b) for i, n, v, b in cats]
    expenses = sum((c.expenses for c in by), D("0.00"))
    return MonthSummary(name, D(income), expenses, D(income) - expenses, D(income) - expenses, by)


def test_averages():
    s = [
        _month(
            "2025-03", "5000", [(1, "Jedzenie", "300.00", True), (9, "Inwestycje", "99", False)]
        ),
        _month("2025-02", "3000", [(1, "Jedzenie", "100.00", True)]),
    ]
    assert average_by_category(s) == {1: ("Jedzenie", D("200.00"))}
    assert 9 in average_by_category(s, budget_only=False)
    income, expenses, surplus = average_totals(s)
    assert income == D("4000.00") and expenses == D("249.50")
    assert surplus == D("3750.50")
    assert average_totals([]) == (D("0.00"),) * 3 and average_by_category([]) == {}


def test_month_helpers():
    assert previous_month(date(2025, 1, 15)) == "2024-12"
    assert previous_month(date(2025, 7, 1)) == "2025-06"
    assert shift_month("2025-01", -2) == "2024-11" and shift_month("2025-11", 3) == "2026-02"
