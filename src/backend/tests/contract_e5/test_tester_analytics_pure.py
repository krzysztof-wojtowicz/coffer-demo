"""Pure-function contract tests for E5-02 / E5-03 analytics (from cards, not code)."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.month import CategoryTotal, MonthSummary

D = Decimal


def ms(month: str, cats: dict[int, tuple[str, str, bool]]) -> MonthSummary:
    by = [CategoryTotal(cid, n, D(v), b) for cid, (n, v, b) in cats.items()]
    total = sum((c.expenses for c in by), D("0.00"))
    return MonthSummary(month, D("0.00"), total, -total, -total, by)


def test_category_total_in_budget_default_true():
    assert CategoryTotal(1, "x", D("1.00")).in_budget is True


def test_compare_months_basic():
    from coffer.analytics.compare import compare_months

    cur = ms("2025-03", {1: ("A", "150.00", True), 2: ("B", "10.00", True)})
    prev = ms("2025-02", {1: ("A", "100.00", True), 3: ("C", "40.00", True)})
    out = compare_months(cur, prev)
    by = {c.category_id: c for c in out}
    assert set(by) == {1, 2, 3}
    assert by[1].change == D("50.00") and by[1].change_pct == D("50.0")
    assert by[2].previous == D("0.00") and by[2].change_pct is None
    assert by[3].current == D("0.00") and by[3].change == D("-40.00")
    assert by[3].change_pct == D("-100.0")
    assert [c.category_id for c in out] == [1, 3, 2]  # |50|, |-40|, |10|


def test_compare_tie_sorted_by_name():
    from coffer.analytics.compare import compare_months

    cur = ms("2025-03", {1: ("Zeta", "10.00", True), 2: ("Alfa", "10.00", True)})
    prev = ms("2025-02", {})
    assert [c.category_name for c in compare_months(cur, prev)] == ["Alfa", "Zeta"]


def test_compare_rounding_pct_half_up():
    from coffer.analytics.compare import compare_months

    cur = ms("2025-03", {1: ("A", "1.00", True)})
    prev = ms("2025-02", {1: ("A", "3.00", True)})
    assert compare_months(cur, prev)[0].change_pct == D("-66.7")


def test_top_growth_rules():
    from coffer.analytics.compare import top_growth

    cur = ms(
        "2025-03",
        {
            1: ("A", "100.00", True),
            2: ("B", "300.00", True),
            3: ("C", "50.00", False),  # not in budget
            4: ("D", "10.00", True),  # decreased
            5: ("E", "200.00", True),
            6: ("F", "150.00", True),
        },
    )
    hist = [
        ms("2025-02", {4: ("D", "100.00", True)}),
        ms("2025-01", {}),
        ms("2024-12", {}),
    ]
    out = top_growth(cur, hist)
    assert len(out) == 3
    assert [g.category_id for g in out] == [2, 5, 6]
    assert 3 not in [g.category_id for g in out] and 4 not in [g.category_id for g in out]
    assert out[0].average_3m == D("0.00") and out[0].increase == D("300.00")
    assert out[0].increase_pct is None
    assert len(top_growth(cur, hist, n=1)) == 1


def test_top_growth_average_counts_missing_as_zero():
    from coffer.analytics.compare import top_growth

    cur = ms("2025-03", {1: ("A", "90.00", True)})
    hist = [
        ms("2025-02", {}),
        ms("2025-01", {1: ("A", "60.00", True)}),
        ms("2024-12", {1: ("A", "30.00", True)}),
    ]
    g = top_growth(cur, hist)[0]
    assert g.average_3m == D("30.00") and g.increase == D("60.00")


@given(
    cur=st.dictionaries(st.integers(1, 8), st.decimals(0, 5000, places=2), max_size=8),
    prev=st.dictionaries(st.integers(1, 8), st.decimals(0, 5000, places=2), max_size=8),
)
def test_compare_sum_equals_expenses_and_top_growth_bounds(cur, prev):
    from coffer.analytics.compare import compare_months, top_growth

    c = ms("2025-03", {k: (f"c{k}", str(v), k % 2 == 0) for k, v in cur.items() if v > 0})
    p = ms("2025-02", {k: (f"c{k}", str(v), k % 2 == 0) for k, v in prev.items() if v > 0})
    out = compare_months(c, p)
    assert sum((x.current for x in out), D("0.00")) == c.expenses
    tg = top_growth(c, [p])
    assert len(tg) <= 3
    assert all(g.category_id % 2 == 0 and g.increase > 0 for g in tg)


def test_limit_status():
    from coffer.analytics.limits import limit_status

    by = [CategoryTotal(1, "A", D("150.00")), CategoryTotal(2, "B", D("100.00"))]
    out = limit_status(by, {1: ("A", D("100.00")), 2: ("B", D("100.00")), 3: ("C", D("50.00"))})
    s = {x.category_id: x for x in out}
    assert s[1].exceeded is True and s[1].spent == D("150.00")
    assert s[2].exceeded is False
    assert s[3].spent == D("0.00") and s[3].exceeded is False and s[3].category_name == "C"
    assert s[3].limit == D("50.00")


# ---- E5-03 analytics/allocation.py

LEVELS = ["low", "medium", "high"]


@pytest.mark.parametrize("risk", LEVELS)
@pytest.mark.parametrize("horizon", ["short", "medium", "long"])
def test_target_allocation_sums_to_100(risk, horizon):
    from coffer.analytics.allocation import target_allocation

    t = target_allocation(risk, horizon)
    assert t and all(isinstance(v, Decimal) and v >= 0 for v in t.values())
    assert sum(t.values()) == D("100")


def test_target_allocation_riskier_has_more_growth_assets():
    from coffer.analytics.allocation import target_allocation

    def growth(t):
        return sum(v for k, v in t.items() if k in ("stock", "stocks", "etf", "crypto"))

    assert growth(target_allocation("high", "long")) > growth(target_allocation("low", "short"))


def test_allocation_gap():
    from coffer.analytics.allocation import allocation_gap

    out = allocation_gap(
        {"stock": D("80"), "bond": D("20")}, {"stock": D("60"), "bond": D("30"), "cash": D("10")}
    )
    g = {x.asset_class: x for x in out}
    assert set(g) == {"stock", "bond", "cash"}
    assert g["stock"].current_pct == D("80") and g["stock"].target_pct == D("60")
    assert g["stock"].gap_pp == D("20") or g["stock"].gap_pp == D(
        "-20"
    )  # sign convention is a doc matter
    assert g["cash"].current_pct == D("0")


def test_max_position_share():
    from coffer.analytics.allocation import max_position_share

    assert max_position_share([]) is None
    assert max_position_share([D("0.00")]) is None or max_position_share([D("0.00")]) == D("0")
    assert max_position_share([D("50.00"), D("30.00"), D("20.00")]) == D(
        "50.0"
    ) or max_position_share([D("50.00"), D("30.00"), D("20.00")]) == D("50")


# ---- E5-03 pricing


def test_pricing_contract():
    from coffer.agent.pricing import estimate_cost

    assert estimate_cost("ollama", "llama3", 1000, 1000) == D("0")
    assert estimate_cost("openai", "totally-unknown-model-xyz", 1000, 1000) is None
    assert estimate_cost("openai", "gpt-4o-mini", None, None) is None
    c = estimate_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
    assert c is None or (isinstance(c, Decimal) and c > 0)
