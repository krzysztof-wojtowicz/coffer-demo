from datetime import date
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.compare import compare_months, top_growth
from coffer.analytics.month import TxView, month_summary

CATS = [(1, "A", True), (2, "B", True), (3, "Inwestycje", False)]


def _summary(month: str, items: list[tuple[int, int]]):
    txs = [TxView(date.fromisoformat(f"{month}-05"), -Decimal(c) / 100, *CATS[i]) for i, c in items]
    return month_summary(month, txs)


amounts = st.lists(st.tuples(st.integers(0, 2), st.integers(1, 10**7)), max_size=15)


@given(amounts, amounts)
def test_comparison_sums_to_expenses(cur, prev):
    c, p = _summary("2026-03", cur), _summary("2026-02", prev)
    assert sum((x.current for x in compare_months(c, p)), Decimal("0.00")) == c.expenses


@given(amounts, st.lists(amounts, min_size=3, max_size=3))
def test_top_growth_limited_and_budget_only(cur, hist):
    c = _summary("2026-03", cur)
    result = top_growth(c, [_summary("2026-02", h) for h in hist])
    assert len(result) <= 3
    assert all(g.category_id != 3 and g.increase > 0 for g in result)


def test_pct_none_when_previous_zero():
    c, p = _summary("2026-03", [(0, 1000)]), _summary("2026-02", [])
    [row] = compare_months(c, p)
    assert row.change == Decimal("10.00") and row.change_pct is None


def test_change_pct_and_sorting():
    c = _summary("2026-03", [(0, 15000), (1, 1000)])
    p = _summary("2026-02", [(0, 10000), (1, 5000)])
    rows = compare_months(c, p)
    assert [r.category_name for r in rows] == ["A", "B"]
    assert rows[0].change_pct == Decimal("50.0")


def test_change_pct_rounds_half_up():
    c, p = _summary("2026-03", [(0, 11225)]), _summary("2026-02", [(0, 10000)])
    [row] = compare_months(c, p)
    assert row.change_pct == Decimal("12.3")
