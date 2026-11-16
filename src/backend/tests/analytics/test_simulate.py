from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.simulate import ClassValue, simulate_purchase

D = Decimal
CLASSES = ["stock", "etf", "bond", "real_estate", "commodity", "crypto", "cash"]


def test_adds_to_existing_class():
    impact = simulate_purchase(
        [ClassValue("stock", D("600")), ClassValue("bond", D("400"))], "stock", D("1000")
    )
    assert impact.total_before == D("1000.00") and impact.total_after == D("2000.00")
    assert {s.asset_class: s.share_pct for s in impact.before} == {
        "stock": D("60.0"),
        "bond": D("40.0"),
    }
    assert {s.asset_class: s.share_pct for s in impact.after} == {
        "stock": D("80.0"),
        "bond": D("20.0"),
    }
    assert impact.new_class is False


def test_new_class():
    impact = simulate_purchase([ClassValue("stock", D("100"))], "crypto", D("100"))
    assert impact.new_class is True
    assert {s.asset_class: s.share_pct for s in impact.after} == {
        "stock": D("50.0"),
        "crypto": D("50.0"),
    }


def test_empty_portfolio_is_new_class_100():
    impact = simulate_purchase([], "etf", D("250.50"))
    assert impact.before == [] and impact.new_class is True
    assert [(s.asset_class, s.share_pct, s.value) for s in impact.after] == [
        ("etf", D("100.0"), D("250.50"))
    ]
    assert impact.total_before == D("0.00") and impact.total_after == D("250.50")


@pytest.mark.parametrize("amount", [D("0"), D("-5")])
def test_amount_must_be_positive(amount):
    with pytest.raises(ValueError):
        simulate_purchase([], "etf", amount)


@given(
    values=st.lists(st.decimals(min_value=D("0.01"), max_value=D("1000000"), places=2), max_size=7),
    amount=st.decimals(min_value=D("0.01"), max_value=D("1000000"), places=2),
    cls=st.sampled_from(CLASSES),
)
def test_hypothesis_shares_sum_to_100(values, amount, cls):
    classes = [ClassValue(CLASSES[i], v) for i, v in enumerate(values)]
    impact = simulate_purchase(classes, cls, amount)
    assert impact.total_after == impact.total_before + amount
    assert abs(sum(s.share_pct for s in impact.after) - 100) <= D("0.1")
    if impact.before:
        assert abs(sum(s.share_pct for s in impact.before) - 100) <= D("0.1")
