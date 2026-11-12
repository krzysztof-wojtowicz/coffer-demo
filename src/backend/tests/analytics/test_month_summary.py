import dataclasses
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.month import CategoryTotal, MonthSummary, TxView, month_summary

D = Decimal


def tx(day, amount, cid=1, name="Jedzenie", in_budget=True):
    return TxView(
        date=day, base_amount=D(amount), category_id=cid, category_name=name, in_budget=in_budget
    )


M = "2026-03"


def test_empty_month():
    s = month_summary(M, [])
    assert s == MonthSummary(
        month=M,
        income=D("0.00"),
        expenses=D("0.00"),
        balance=D("0.00"),
        surplus=D("0.00"),
        by_category=[],
    )


def test_basic():
    s = month_summary(
        M,
        [
            tx(date(2026, 3, 1), "5000.00", 9, "Pensja"),
            tx(date(2026, 3, 5), "-100.50"),
            tx(date(2026, 3, 6), "-49.50"),
            tx(date(2026, 3, 7), "-200", 2, "Transport"),
        ],
    )
    assert s.income == D("5000.00")
    assert s.expenses == D("350.00")
    assert s.balance == D("4650.00")
    assert s.surplus == D("4650.00")
    assert s.by_category == [
        CategoryTotal(2, "Transport", D("200.00")),
        CategoryTotal(1, "Jedzenie", D("150.00")),
    ]


def test_only_expenses():
    s = month_summary(M, [tx(date(2026, 3, 2), "-10.00")])
    assert s.income == D("0.00")
    assert s.expenses == D("10.00")
    assert s.balance == D("-10.00")
    assert s.surplus == D("0.00")


def test_deficit():
    s = month_summary(
        M, [tx(date(2026, 3, 2), "100.00", 9, "Pensja"), tx(date(2026, 3, 3), "-250.00")]
    )
    assert s.balance == D("-150.00")
    assert s.surplus == D("0.00")
    assert s.expenses == D("250.00")


def test_outside_month_ignored():
    s = month_summary(
        M,
        [
            tx(date(2026, 2, 28), "-100"),
            tx(date(2026, 4, 1), "-100"),
            tx(date(2025, 3, 15), "-100"),
            tx(date(2026, 3, 1), "-1"),
            tx(date(2026, 3, 31), "-2"),
        ],
    )
    assert s.expenses == D("3.00")


def test_not_in_budget_counted_but_not_in_surplus():
    s = month_summary(
        M,
        [
            tx(date(2026, 3, 2), "-500", 7, "Inwestycje", in_budget=False),
            tx(date(2026, 3, 2), "500", 8, "Przelewy własne", in_budget=False),
            tx(date(2026, 3, 3), "-5"),
        ],
    )
    assert s.income == D("500.00")
    assert s.expenses == D("505.00")
    assert s.balance == D("-5.00")
    assert s.surplus == D("0.00")
    assert [c.category_name for c in s.by_category] == ["Inwestycje", "Jedzenie"]


def test_surplus_ignores_out_of_budget_investment():
    s = month_summary(
        M,
        [
            tx(date(2026, 3, 2), "1000", 9, "Pensja"),
            tx(date(2026, 3, 3), "-500", 7, "Inwestycje", in_budget=False),
        ],
    )
    assert s.balance == D("500.00")
    assert s.surplus == D("1000.00")


def test_cents_exact():
    s = month_summary(M, [tx(date(2026, 3, 2), "-0.10"), tx(date(2026, 3, 3), "-0.20")])
    assert s.expenses == D("0.30")
    assert s.by_category[0].expenses == D("0.30")
    s = month_summary(
        M, [tx(date(2026, 3, 2), "0.10", 9, "P"), tx(date(2026, 3, 3), "0.20", 9, "P")]
    )
    assert s.income == D("0.30")


def test_quantized_two_places():
    s = month_summary(M, [tx(date(2026, 3, 2), "-5"), tx(date(2026, 3, 2), "10", 9, "P")])
    for v in (s.income, s.expenses, s.balance, s.surplus, s.by_category[0].expenses):
        assert v.as_tuple().exponent == -2
    assert str(s.income) == "10.00"
    assert not any(isinstance(v, float) for v in (s.income, s.expenses))


def test_category_sorting_ties_by_name():
    s = month_summary(
        M,
        [
            tx(date(2026, 3, 2), "-10", 1, "Zakupy"),
            tx(date(2026, 3, 2), "-10", 2, "Auto"),
            tx(date(2026, 3, 2), "-30", 3, "Dom"),
        ],
    )
    assert [c.category_name for c in s.by_category] == ["Dom", "Auto", "Zakupy"]


def test_income_only_category_not_in_by_category():
    s = month_summary(M, [tx(date(2026, 3, 2), "100", 9, "Pensja")])
    assert s.by_category == []


def test_refund_in_expense_category_nets_out():
    # Zwrot (dodatni) liczy się jako przychód, wydatki to suma ujemnych.
    s = month_summary(M, [tx(date(2026, 3, 2), "-100"), tx(date(2026, 3, 3), "30")])
    assert s.income == D("30.00")
    assert s.expenses == D("100.00")


def test_accepts_iterator():
    s = month_summary(M, iter([tx(date(2026, 3, 2), "-1")]))
    assert s.expenses == D("1.00")


def test_frozen():
    t = tx(date(2026, 3, 2), "-1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.base_amount = D("1")  # type: ignore[misc]


amounts = st.decimals(min_value=D("-100000"), max_value=D("100000"), places=2)
tx_strategy = st.builds(
    TxView,
    date=st.dates(min_value=date(2026, 2, 25), max_value=date(2026, 4, 5)),
    base_amount=amounts,
    category_id=st.integers(1, 4),
    category_name=st.sampled_from(["A", "B", "C", "D"]),
    in_budget=st.booleans(),
)


@given(st.lists(tx_strategy, max_size=40))
def test_invariants(txs):
    s = month_summary(M, txs)
    assert s.income - s.expenses == s.balance
    assert sum((c.expenses for c in s.by_category), D("0.00")) == s.expenses
    assert s.surplus >= 0
    budget_bal = sum(
        (t.base_amount for t in txs if t.in_budget and t.date.strftime("%Y-%m") == M), D("0.00")
    )
    assert s.surplus == max(budget_bal, D("0"))
    assert s.income >= 0 and s.expenses >= 0
    assert all(c.expenses > 0 for c in s.by_category)
    keys = [(-c.expenses, c.category_name) for c in s.by_category]
    assert keys == sorted(keys)
    relevant = [t for t in txs if t.date.strftime("%Y-%m") == M]
    assert s.income == sum((t.base_amount for t in relevant if t.base_amount > 0), D("0.00"))
    assert s.expenses == -sum((t.base_amount for t in relevant if t.base_amount < 0), D("0.00"))
