"""Pure analytics functions (no DB, no FastAPI): month summary, comparison, limits, net worth,
portfolio valuation."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.compare import compare_months, top_growth
from coffer.analytics.limits import limit_status
from coffer.analytics.month import CategoryTotal, MonthSummary, TxView, month_summary
from coffer.analytics.net_worth import net_worth, portfolio_is_complete
from coffer.analytics.portfolio import (
    ClassAllocation,
    HoldingInput,
    gain_pct,
    portfolio_summary,
    value_holding,
)

D = Decimal
M = "2026-03"


def tx(day, amount, cid=1, name="Jedzenie", in_budget=True):
    return TxView(
        date=day, amount=D(amount), category_id=cid, category_name=name, in_budget=in_budget
    )


# --- month_summary ---


def test_empty_month():
    assert month_summary(M, []) == MonthSummary(
        month=M,
        income=D("0.00"),
        expenses=D("0.00"),
        balance=D("0.00"),
        surplus=D("0.00"),
        by_category=[],
    )


def test_basic_totals_and_category_order():
    s = month_summary(
        M,
        [
            tx(date(2026, 3, 1), "5000.00", 9, "Pensja"),
            tx(date(2026, 3, 5), "-100.50"),
            tx(date(2026, 3, 6), "-49.50"),
            tx(date(2026, 3, 7), "-200", 2, "Transport"),
            tx(date(2026, 3, 8), "30", 1),  # a refund counts as income
        ],
    )
    assert s.income == D("5030.00")
    assert s.expenses == D("350.00")
    assert s.balance == D("4680.00")
    assert s.surplus == D("4680.00")
    assert s.by_category == [
        CategoryTotal(2, "Transport", D("200.00")),
        CategoryTotal(1, "Jedzenie", D("150.00")),
    ]


def test_deficit_surplus_is_zero():
    s = month_summary(
        M, [tx(date(2026, 3, 2), "100.00", 9, "Pensja"), tx(date(2026, 3, 3), "-250.00")]
    )
    assert (s.balance, s.surplus, s.expenses) == (D("-150.00"), D("0.00"), D("250.00"))


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
            tx(date(2026, 3, 1), "1000", 9, "Pensja"),
            tx(date(2026, 3, 2), "-500", 7, "Inwestycje", in_budget=False),
            tx(date(2026, 3, 2), "500", 8, "Przelewy własne", in_budget=False),
            tx(date(2026, 3, 3), "-5"),
        ],
    )
    assert s.income == D("1500.00")
    assert s.expenses == D("505.00")
    assert s.balance == D("995.00")
    assert s.surplus == D("995.00")
    assert [c.category_name for c in s.by_category] == ["Inwestycje", "Jedzenie"]


def test_cents_exact_quantized_and_never_float():
    s = month_summary(
        M,
        [
            tx(date(2026, 3, 2), "-0.10"),
            tx(date(2026, 3, 3), "-0.20"),
            tx(date(2026, 3, 3), "0.10", 9, "P"),
            tx(date(2026, 3, 3), "10", 9, "P"),
        ],
    )
    assert s.expenses == s.by_category[0].expenses == D("0.30")
    assert s.income == D("10.10")
    for v in (s.income, s.expenses, s.balance, s.surplus, s.by_category[0].expenses):
        assert isinstance(v, Decimal) and v.as_tuple().exponent == -2


def test_category_sorting_ties_by_name_and_income_only_excluded():
    s = month_summary(
        M,
        [
            tx(date(2026, 3, 2), "-10", 1, "Zakupy"),
            tx(date(2026, 3, 2), "-10", 2, "Auto"),
            tx(date(2026, 3, 2), "-30", 3, "Dom"),
            tx(date(2026, 3, 2), "100", 9, "Pensja"),
        ],
    )
    assert [c.category_name for c in s.by_category] == ["Dom", "Auto", "Zakupy"]


amounts = st.decimals(min_value=D("-100000"), max_value=D("100000"), places=2)
tx_strategy = st.builds(
    TxView,
    date=st.dates(min_value=date(2026, 2, 25), max_value=date(2026, 4, 5)),
    amount=amounts,
    category_id=st.integers(1, 4),
    category_name=st.sampled_from(["A", "B", "C", "D"]),
    in_budget=st.booleans(),
)


@given(st.lists(tx_strategy, max_size=40))
def test_month_summary_invariants_n04(txs):
    s = month_summary(M, txs)
    assert s.income - s.expenses == s.balance
    assert sum((c.expenses for c in s.by_category), D("0.00")) == s.expenses
    assert s.surplus >= 0
    relevant = [t for t in txs if t.date.strftime("%Y-%m") == M]
    budget_bal = sum((t.amount for t in relevant if t.in_budget), D("0.00"))
    assert s.surplus == max(budget_bal, D("0"))
    assert all(c.expenses > 0 for c in s.by_category)
    keys = [(-c.expenses, c.category_name) for c in s.by_category]
    assert keys == sorted(keys)
    assert s.income == sum((t.amount for t in relevant if t.amount > 0), D("0.00"))
    assert s.expenses == -sum((t.amount for t in relevant if t.amount < 0), D("0.00"))


# --- compare_months / top_growth ---


def ms(month: str, cats: dict[int, tuple[str, str, bool]]) -> MonthSummary:
    by = [CategoryTotal(cid, n, D(v), b) for cid, (n, v, b) in cats.items()]
    total = sum((c.expenses for c in by), D("0.00"))
    return MonthSummary(month, D("0.00"), total, -total, -total, by)


def test_category_total_in_budget_default_true():
    assert CategoryTotal(1, "x", D("1.00")).in_budget is True


def test_compare_months_changes_and_order():
    cur = ms("2025-03", {1: ("A", "150.00", True), 2: ("B", "10.00", True)})
    prev = ms("2025-02", {1: ("A", "100.00", True), 3: ("C", "40.00", True)})
    out = compare_months(cur, prev)
    by = {c.category_id: c for c in out}
    assert set(by) == {1, 2, 3}
    assert by[1].change == D("50.00") and by[1].change_pct == D("50.0")
    assert by[2].previous == D("0.00") and by[2].change_pct is None
    assert by[3].current == D("0.00") and by[3].change == D("-40.00")
    assert by[3].change_pct == D("-100.0")
    assert [c.category_id for c in out] == [1, 3, 2]  # by |change|


def test_compare_tie_sorted_by_name():
    cur = ms("2025-03", {1: ("Zeta", "10.00", True), 2: ("Alfa", "10.00", True)})
    assert [c.category_name for c in compare_months(cur, ms("2025-02", {}))] == ["Alfa", "Zeta"]


@pytest.mark.parametrize(
    ("current", "previous", "pct"),
    [("112.25", "100.00", "12.3"), ("1.00", "3.00", "-66.7"), ("5.00", "5.00", "0.0")],
)
def test_change_pct_rounds_half_up(current, previous, pct):
    [row] = compare_months(
        ms("2025-03", {1: ("A", current, True)}), ms("2025-02", {1: ("A", previous, True)})
    )
    assert row.change_pct == D(pct)


def test_top_growth_rules():
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
    hist = [ms("2025-02", {4: ("D", "100.00", True)}), ms("2025-01", {}), ms("2024-12", {})]
    out = top_growth(cur, hist)
    assert [g.category_id for g in out] == [2, 5, 6]
    assert out[0].average_3m == D("0.00") and out[0].increase == D("300.00")
    assert out[0].increase_pct is None
    assert len(top_growth(cur, hist, n=1)) == 1


def test_top_growth_average_counts_missing_months_as_zero():
    cur = ms("2025-03", {1: ("A", "90.00", True)})
    hist = [
        ms("2025-02", {}),
        ms("2025-01", {1: ("A", "60.00", True)}),
        ms("2024-12", {1: ("A", "30.00", True)}),
    ]
    g = top_growth(cur, hist)[0]
    assert g.average_3m == D("30.00") and g.increase == D("60.00")


def test_top_growth_with_fewer_than_three_months_uses_available():
    cur = ms("2025-03", {1: ("A", "90.00", True)})
    g = top_growth(cur, [ms("2025-02", {1: ("A", "60.00", True)})])[0]
    assert g.average_3m == D("60.00") and g.increase == D("30.00")


CATS = [(1, "A", True), (2, "B", True), (3, "Inwestycje", False)]


def _summary(month: str, items: list[tuple[int, int]]):
    txs = [TxView(date.fromisoformat(f"{month}-05"), -D(c) / 100, *CATS[i]) for i, c in items]
    return month_summary(month, txs)


month_items = st.lists(st.tuples(st.integers(0, 2), st.integers(1, 10**7)), max_size=15)


@given(month_items, month_items)
def test_comparison_sums_to_expenses(cur, prev):
    c, p = _summary("2026-03", cur), _summary("2026-02", prev)
    assert sum((x.current for x in compare_months(c, p)), D("0.00")) == c.expenses


@given(month_items, st.lists(month_items, min_size=3, max_size=3))
def test_top_growth_limited_and_budget_only(cur, hist):
    result = top_growth(_summary("2026-03", cur), [_summary("2026-02", h) for h in hist])
    assert len(result) <= 3
    assert all(g.category_id != 3 and g.increase > 0 for g in result)


# --- limit_status ---


@pytest.mark.parametrize(
    ("spent", "limit", "exceeded", "remaining", "used_pct"),
    [
        ("150.00", "100.00", True, "-50.00", "150.0"),
        ("100.00", "100.00", False, "0.00", "100.0"),
        ("12.25", "100.00", False, "87.75", "12.3"),
        ("0.00", "50.00", False, "50.00", "0.0"),
    ],
)
def test_limit_status(spent, limit, exceeded, remaining, used_pct):
    by = [CategoryTotal(1, "A", D(spent))] if D(spent) else []
    [s] = limit_status(by, {1: ("A", D(limit))})
    assert s.exceeded is exceeded
    assert (s.spent, s.limit, s.remaining, s.used_pct) == (
        D(spent),
        D(limit),
        D(remaining),
        D(used_pct),
    )
    assert s.category_name == "A"


# --- net_worth ---


def test_net_worth_sum_and_rounding():
    n = net_worth([D("100.005"), D("-30.00")], D("50.004"), True)
    assert (n.cash_balance, n.portfolio_value, n.net_worth) == (D("70.01"), D("50.00"), D("120.01"))
    assert n.portfolio_complete is True
    assert net_worth([], D("0"), True).net_worth == D("0.00")


def _holding(**kw):
    base = dict(
        id=1, name="a", symbol="AAPL", asset_class="stock", quantity=D("1"), purchase_price=D("10")
    )
    return HoldingInput(**{**base, **kw})


def test_portfolio_completeness():
    assert portfolio_is_complete(portfolio_summary([_holding(market_price=D("12"))]), True)
    assert not portfolio_is_complete(portfolio_summary([_holding()]), False)
    assert portfolio_is_complete(portfolio_summary([_holding(symbol=None)]), False)
    assert not portfolio_is_complete(
        portfolio_summary([_holding(symbol=None, currency="USD")]), True
    )


# --- portfolio valuation ---


def h(
    id=1,
    cls="stock",
    qty="10",
    price="100.00",
    manual=None,
    market=None,
    symbol="ABC",
    ccy="PLN",
    price_ccy=None,
):
    return HoldingInput(
        id=id,
        name=f"H{id}",
        symbol=symbol,
        asset_class=cls,
        quantity=D(qty),
        purchase_price=D(price),
        manual_value=D(manual) if manual is not None else None,
        market_price=D(market) if market is not None else None,
        currency=ccy,
        price_currency=price_ccy,
    )


def cv(holding, fx=None):
    v = value_holding(holding, fx)
    return v.value, v.source


def test_empty_portfolio():
    s = portfolio_summary([])
    assert s.holdings == []
    assert s.allocation == []
    assert s.total_value == D("0.00")
    assert s.total_cost == D("0.00")
    assert s.total_gain == D("0.00")
    assert s.total_gain_pct is None


def test_value_priority_market_manual_cost():
    assert cv(h(market="120.50", manual="5")) == (D("1205.00"), "market")
    assert cv(h(manual="500000")) == (D("500000.00"), "manual")
    assert cv(h()) == (D("1000.00"), "cost")


@pytest.mark.parametrize(
    ("market", "gain", "pct"), [("110", "100.00", "10.0"), ("75", "-250.00", "-25.0")]
)
def test_gain_and_loss(market, gain, pct):
    v = portfolio_summary([h(market=market)]).holdings[0]
    assert v.cost_basis == D("1000.00")
    assert (v.gain, v.gain_pct, v.share_pct) == (D(gain), D(pct), D("100.0"))


def test_gain_pct_none_for_zero_cost():
    assert gain_pct(D("10"), D("0")) is None
    assert portfolio_summary([h(price="0", manual="100")]).holdings[0].gain_pct is None


def test_fractional_quantity_rounds_half_up():
    v = portfolio_summary([h(cls="crypto", qty="0.005", price="1.00", market="1.00")]).holdings[0]
    assert v.current_value == D("0.01")  # 0.005 -> half-up


def test_allocation_by_class_sorted_desc():
    s = portfolio_summary(
        [
            h(1, "stock", "1", "100", market="100"),
            h(2, "etf", "1", "100", market="300"),
            h(3, "stock", "1", "100", market="100"),
            h(4, "real_estate", "1", "500000", manual="0"),
        ]
    )
    assert s.allocation == [
        ClassAllocation("etf", D("300.00"), D("60.0")),
        ClassAllocation("stock", D("200.00"), D("40.0")),
        ClassAllocation("real_estate", D("0.00"), D("0.0")),
    ]
    assert s.total_value == D("500.00")
    assert s.total_cost == D("500300.00")
    assert s.total_gain == D("-499800.00")


money = st.decimals(min_value=0, max_value=10**6, places=2, allow_nan=False)
qty = st.decimals(min_value=D("0.00000001"), max_value=10**4, places=8, allow_nan=False)


@given(st.lists(st.tuples(qty, money, st.one_of(st.none(), money)), max_size=8))
def test_totals_are_consistent(rows):
    items = [
        h(i, "stock" if i % 2 else "etf", str(q), str(p), market=m)
        for i, (q, p, m) in enumerate(rows)
    ]
    s = portfolio_summary(items)
    assert s.total_value == sum((v.current_value for v in s.holdings), D("0.00"))
    assert s.total_value == sum((a.value for a in s.allocation), D("0.00"))
    assert s.total_gain == s.total_value - s.total_cost
    for v in s.holdings:
        assert v.current_value == v.current_value.quantize(D("0.01"))


USD = {"USD": D("4")}


def test_market_price_in_usd_converted_to_pln():
    s = portfolio_summary([h(qty="2", price="700.00", market="200", price_ccy="USD")], USD)
    v = s.holdings[0]
    assert v.current_value == D("1600.00")
    assert v.value_source == "market"
    assert v.cost_basis == D("1400.00")
    assert v.amount_currency == "PLN" and v.converted
    assert s.total_value == D("1600.00")
    assert s.fx_missing == []


def test_usd_holding_cost_and_manual_converted():
    v = portfolio_summary([h(qty="2", price="150.00", ccy="USD")], USD).holdings[0]
    assert (v.cost_basis, v.current_value, v.value_source) == (D("1200.00"), D("1200.00"), "cost")
    m = portfolio_summary([h(qty="1", price="100", manual="250.50", ccy="USD")], USD)
    assert m.holdings[0].current_value == D("1002.00")


def test_missing_quote_rate_falls_back_and_flags():
    s = portfolio_summary([h(qty="2", price="700.00", market="200", price_ccy="USD")], {})
    v = s.holdings[0]
    assert v.value_source == "cost"
    assert v.current_value == D("1400.00")
    assert s.fx_missing == ["USD"]
    assert s.total_value == D("1400.00")


def test_missing_holding_rate_excluded_from_totals():
    s = portfolio_summary(
        [h(1, qty="1", price="100"), h(2, qty="1", price="50", ccy="CHF", market="60",
                                       price_ccy="CHF")],
        {},
    )  # fmt: skip
    pln, chf = s.holdings
    assert chf.converted is False and chf.amount_currency == "CHF"
    assert chf.value_source == "market" and chf.current_value == D("60.00")
    assert chf.share_pct is None
    assert pln.share_pct == D("100.0")
    assert s.total_value == D("100.00")
    assert [a.asset_class for a in s.allocation] == ["stock"]
    assert s.fx_missing == ["CHF"]


@given(st.lists(tx_strategy, max_size=40))
def test_monthly_balances_sum_to_all_transactions_n04(txs):
    months = ["2026-02", "2026-03", "2026-04"]
    inside = [t for t in txs if t.date.strftime("%Y-%m") in months]
    total = sum((month_summary(m, txs).balance for m in months), D("0.00"))
    assert total == sum((t.amount for t in inside), D("0.00"))
