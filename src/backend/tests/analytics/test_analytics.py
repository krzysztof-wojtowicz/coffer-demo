"""Pure analytics functions (no DB, no FastAPI): month summary, comparison, net worth,
portfolio valuation."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.allocation import (
    ASSET_CLASSES,
    allocation_gap,
    target_allocation,
)
from coffer.analytics.month import CategoryTotal, MonthSummary, TxView, month_summary
from coffer.analytics.net_worth import net_worth, portfolio_is_complete
from coffer.analytics.portfolio import (
    ClassAllocation,
    HoldingInput,
    gain_pct,
    portfolio_summary,
    value_holding,
)
from coffer.analytics.trend import trend

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
        budget_income=D("0.00"),
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


# --- trend ---

OWN = (9, "Przelewy własne", False)
INV = (8, "Inwestycje", False)
SAL = (7, "Wynagrodzenie", True)
FOOD = (1, "Jedzenie", True)
CAR = (2, "Transport", True)


def mt(month, *items):
    """Month summary from (amount, (cid, name, in_budget)) items, all dated on the 5th."""
    d = date.fromisoformat(f"{month}-05")
    return month_summary(month, [TxView(d, D(a), *c) for a, c in items])


def test_category_total_in_budget_default_true():
    assert CategoryTotal(1, "x", D("1.00")).in_budget is True


def test_trend_months_oldest_first_and_last_is_month():
    t = trend([mt("2026-01"), mt("2026-02"), mt("2026-03")])
    assert t.month == "2026-03"
    assert [p.month for p in t.months] == ["2026-01", "2026-02", "2026-03"]


def test_trend_savings_rate_example():
    t = trend([mt("2026-03", ("8500.00", SAL), ("-3712.16", FOOD))])
    p = t.months[-1]
    assert p.surplus == D("4787.84")
    assert p.savings_rate == D("56.3")


def test_trend_savings_rate_unchanged_by_own_transfers():
    t = trend(
        [mt("2026-03", ("8500.00", SAL), ("-3712.16", FOOD), ("1000.00", OWN), ("-1000.00", OWN))]
    )
    p = t.months[-1]
    assert p.income == D("9500.00")
    assert p.surplus == D("4787.84")
    assert p.savings_rate == D("56.3")


def test_trend_investment_sale_counts_in_income_not_in_rate():
    t = trend([mt("2026-03", ("8500.00", SAL), ("-3712.16", FOOD), ("2000.00", INV))])
    p = t.months[-1]
    assert p.income == D("10500.00")
    assert p.savings_rate == D("56.3")


def test_trend_savings_rate_null_without_budget_income():
    t = trend([mt("2026-03", ("2000.00", INV), ("500.00", OWN), ("-100.00", FOOD))])
    assert t.months[-1].savings_rate is None
    assert trend([mt("2026-03")]).months[-1].savings_rate is None


def test_trend_average_and_change_example():
    t = trend(
        [
            mt("2026-01", ("-3000.00", FOOD)),
            mt("2026-02", ("-5000.00", FOOD)),
            mt("2026-03", ("-4400.00", FOOD)),
        ]
    )
    assert t.average.expenses == D("4000.00")
    assert t.change.expenses.amount == D("400.00")
    assert t.change.expenses.pct == D("10.0")


def test_trend_empty_earlier_months_not_averaged():
    t = trend(
        [
            mt("2026-01", ("-3000.00", FOOD)),
            mt("2026-02"),
            mt("2026-03"),
            mt("2026-04", ("-4000.00", FOOD)),
        ]
    )
    assert t.average.expenses == D("3000.00")
    assert t.change.expenses.amount == D("1000.00")


def test_trend_no_earlier_data_gives_null_average_and_change():
    t = trend([mt("2026-01"), mt("2026-02"), mt("2026-03", ("-10.00", FOOD))])
    assert t.average is None
    assert t.change is None


def test_trend_average_savings_rate_is_average_surplus_over_average_budget_income():
    t = trend(
        [
            mt("2026-01", ("1000.00", SAL), ("-500.00", FOOD)),
            mt("2026-02", ("3000.00", SAL), ("-2500.00", FOOD)),
            mt("2026-03", ("2000.00", SAL), ("-500.00", FOOD)),
        ]
    )
    # average surplus 500 / average income 2000 = 25.0; this month 75.0 -> +50.0 points
    assert t.average.savings_rate == D("25.0")
    assert t.change.savings_rate.amount == D("50.0")


def test_trend_category_amounts_zero_filled():
    t = trend(
        [
            mt("2026-01", ("-926.09", FOOD)),
            mt("2026-02", ("-5.00", CAR)),
            mt("2026-03", ("-1895.24", FOOD)),
        ]
    )
    food = next(c for c in t.categories if c.category_name == "Jedzenie")
    assert food.amounts == [D("926.09"), D("0.00"), D("1895.24")]


def test_trend_excludes_out_of_budget_categories():
    t = trend([mt("2026-03", ("-500.00", INV), ("-100.00", OWN), ("-10.00", FOOD))])
    assert [c.category_name for c in t.categories] == ["Jedzenie"]


def test_trend_category_average_counts_missing_as_zero_over_months_with_data():
    t = trend(
        [
            mt("2026-01", ("-100.00", FOOD)),
            mt("2026-02"),
            mt("2026-03", ("-10.00", CAR)),
            mt("2026-04", ("-300.00", FOOD)),
        ]
    )
    food = next(c for c in t.categories if c.category_name == "Jedzenie")
    assert food.average == D("50.00")
    assert food.change == D("250.00")
    assert food.change_pct == D("500.0")


def test_trend_new_category_has_zero_average_and_null_pct():
    t = trend([mt("2026-02", ("-10.00", CAR)), mt("2026-03", ("-40.00", FOOD))])
    food = next(c for c in t.categories if c.category_name == "Jedzenie")
    assert food.average == D("0.00")
    assert food.change == D("40.00")
    assert food.change_pct is None


def test_trend_category_ordering():
    zeta, alfa = (11, "Zeta", True), (12, "Alfa", True)
    t = trend(
        [
            mt("2026-02", ("-900.00", CAR), ("-10.00", FOOD)),
            mt("2026-03", ("-50.00", FOOD), ("-50.00", zeta), ("-50.00", alfa), ("-70.00", CAR)),
        ]
    )
    # month expenses desc (Transport 70), then window total desc, then name
    assert [c.category_name for c in t.categories] == ["Transport", "Jedzenie", "Alfa", "Zeta"]


@given(st.lists(tx_strategy, max_size=40))
def test_trend_months_sum_to_all_transactions_n04(txs):
    months = ["2026-02", "2026-03", "2026-04"]
    inside = [t for t in txs if t.date.strftime("%Y-%m") in months]
    t = trend([month_summary(m, txs) for m in months])
    assert sum((p.balance for p in t.months), D("0.00")) == sum(
        (x.amount for x in inside), D("0.00")
    )


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


# --- target allocation and gap ---

HORIZONS = ("short", "medium", "long")
RISKS = ("low", "medium", "high")
ALL = list(ASSET_CLASSES)
BASE = {
    ("low", "short"): dict(stock=1, etf=9, bond=70, cash=20),
    ("low", "medium"): dict(stock=3, etf=22, bond=60, cash=10, commodity=5),
    ("low", "long"): dict(stock=4, etf=31, bond=55, cash=5, commodity=5),
    ("medium", "short"): dict(stock=6, etf=19, bond=55, cash=20),
    ("medium", "medium"): dict(stock=11, etf=34, bond=40, cash=10, commodity=5),
    ("medium", "long"): dict(
        stock=15, etf=45, bond=22, cash=5, crypto=3, commodity=5, real_estate=5
    ),
    ("high", "short"): dict(stock=16, etf=24, bond=40, cash=20),
    ("high", "medium"): dict(stock=26, etf=39, bond=15, cash=10, crypto=5, commodity=5),
    ("high", "long"): dict(stock=30, etf=45, bond=3, cash=5, crypto=7, commodity=5, real_estate=5),
}


def _t(risk, horizon, preferred):
    return {x.asset_class: x.share_pct for x in target_allocation(horizon, risk, preferred)}


def test_asset_classes_shared_list():
    assert list(ASSET_CLASSES) == [
        "stock",
        "etf",
        "bond",
        "real_estate",
        "commodity",
        "crypto",
        "cash",
    ]


@pytest.mark.parametrize(("risk", "horizon"), list(BASE))
def test_base_table_row_sums_to_100_and_matches(risk, horizon):
    got = _t(risk, horizon, ALL)
    assert got == BASE[(risk, horizon)]
    assert sum(got.values()) == 100


def test_target_output_in_list_order():
    out = [x.asset_class for x in target_allocation("long", "medium", ALL)]
    assert out == [c for c in ASSET_CLASSES if c in out]


def test_unselected_stock_goes_to_etf():
    assert _t("medium", "medium", [c for c in ALL if c != "stock"]) == dict(
        etf=45, bond=40, cash=10, commodity=5
    )


@pytest.mark.parametrize(
    ("dropped", "expected"),
    [
        ("commodity", dict(stock=11, etf=34, bond=45, cash=10)),
        ("bond", dict(stock=11, etf=34, cash=50, commodity=5)),
        ("cash", dict(stock=11, etf=34, bond=50, commodity=5)),
    ],
)
def test_redistribution_chains(dropped, expected):
    assert _t("medium", "medium", [c for c in ALL if c != dropped]) == expected


def test_redistribution_crypto_and_real_estate_to_etf():
    got = _t("medium", "long", ["stock", "etf", "bond", "cash", "commodity"])
    assert got == dict(stock=15, etf=53, bond=22, cash=5, commodity=5)


def test_single_class_gets_everything():
    assert _t("high", "long", ["crypto"]) == {"crypto": 100}


def test_chain_without_selected_goes_to_largest_base():
    # commodity -> bond -> cash; neither selected, so the largest base share (etf 34) wins
    got = _t("medium", "medium", ["stock", "etf", "crypto"])
    assert sum(got.values()) == 100 and set(got) <= {"stock", "etf", "crypto"}
    assert got["etf"] > got["stock"]


@given(
    risk=st.sampled_from(RISKS),
    preferred=st.sets(st.sampled_from(ALL), min_size=1),
)
def test_target_sums_to_100_only_selected_positive(risk, preferred):
    for horizon in HORIZONS:
        got = _t(risk, horizon, list(preferred))
        assert sum(got.values()) == 100
        assert set(got) <= preferred
        assert all(isinstance(v, int) and v > 0 for v in got.values())


def _equity(risk, horizon, preferred):
    t = _t(risk, horizon, preferred)
    return t.get("stock", 0) + t.get("etf", 0)


@given(
    risk=st.sampled_from(RISKS),
    preferred=st.sets(st.sampled_from(ALL), min_size=1).filter(
        lambda p: p & {"stock", "etf"} and p & {"bond", "cash"}
    ),
)
def test_longer_horizon_equity_not_lower(risk, preferred):
    p = list(preferred)
    assert _equity(risk, "short", p) <= _equity(risk, "medium", p) <= _equity(risk, "long", p)


def test_bond_cash_chains_end_in_stock():
    assert _t("low", "medium", ["stock", "commodity"]) == {"stock": 95, "commodity": 5}


def _cur(**shares):
    return [ClassAllocation(k, D(v), D(v)) for k, v in shares.items()]


def test_gap_scenario_total_36():
    target = target_allocation("medium", "medium", ALL)
    gap = allocation_gap(_cur(etf="52", bond="20", cash="28"), target)
    by = {c.asset_class: c.gap_pp for c in gap.classes}
    assert by == {
        "etf": D("18"),
        "bond": D("-20"),
        "cash": D("18"),
        "stock": D("-11"),
        "commodity": D("-5"),
    }
    assert gap.total_gap_pp == D("36")


def test_gap_class_only_in_current_has_zero_target():
    target = target_allocation("medium", "medium", ["etf", "bond"])
    gap = allocation_gap(_cur(etf="50", crypto="50"), target)
    crypto = next(c for c in gap.classes if c.asset_class == "crypto")
    assert crypto.target_pct == 0 and crypto.gap_pp == D("50")


def test_gap_empty_portfolio_is_null():
    target = target_allocation("medium", "medium", ALL)
    gap = allocation_gap([], target)
    assert gap is None or (gap.total_gap_pp is None and all(c.gap_pp is None for c in gap.classes))


def test_gap_all_zero_shares_is_null():
    target = target_allocation("medium", "medium", ALL)
    gap = allocation_gap(_cur(etf="0", bond="0"), target)
    assert gap is None or (gap.total_gap_pp is None and all(c.gap_pp is None for c in gap.classes))


# ---- grouped positions (wallet-grouped-positions) ----


def _lot(
    id: int,
    symbol: str | None = "AAPL",
    name: str = "Apple",
    qty: str = "1",
    price: str = "100",
    **kw,
):
    kw.setdefault("asset_class", "stock")
    return HoldingInput(
        id=id, name=name, symbol=symbol, quantity=Decimal(qty), purchase_price=Decimal(price), **kw
    )


def test_positions_same_ticker_grouped():
    items = [
        _lot(1),
        _lot(2),
        _lot(3),
        _lot(4, symbol="VWCE.DE", name="VWCE", asset_class="etf"),
    ]
    pos = {p.symbol: p for p in portfolio_summary(items).positions}
    assert set(pos) == {"AAPL", "VWCE.DE"}
    assert [lot.holding_id for lot in pos["AAPL"].lots] == [1, 2, 3]
    assert len(pos["VWCE.DE"].lots) == 1


def test_positions_ticker_case_and_spaces_ignored():
    items = [_lot(1, symbol="aapl"), _lot(2, symbol=" AAPL ")]
    positions = portfolio_summary(items).positions
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert len(positions[0].lots) == 2


def test_positions_without_ticker_are_separate():
    items = [
        _lot(1, symbol=None, name="Flat A", asset_class="real_estate"),
        _lot(2, symbol=None, name="Flat B", asset_class="real_estate"),
    ]
    positions = portfolio_summary(items).positions
    assert len(positions) == 2
    assert all(len(p.lots) == 1 for p in positions)


def test_positions_different_currencies_grouped():
    items = [_lot(1, currency="USD"), _lot(2, currency="PLN")]
    positions = portfolio_summary(items, {"USD": Decimal("4")}).positions
    assert len(positions) == 1
    assert {lot.currency for lot in positions[0].lots} == {"USD", "PLN"}


def test_positions_newest_name_and_class():
    items = [
        _lot(1, name="Apple", asset_class="stock", purchase_date=date(2024, 1, 1)),
        _lot(2, name="Apple Inc.", asset_class="etf", purchase_date=date(2025, 1, 1)),
    ]
    p = portfolio_summary(items).positions[0]
    assert p.name == "Apple Inc."
    assert p.asset_class == "etf"


def test_positions_totals():
    items = [
        _lot(1, qty="5", price="600", manual_value=Decimal("4000")),
        _lot(2, qty="5", price="400", manual_value=Decimal("2000")),
        _lot(3, symbol=None, name="Gotówka", asset_class="cash", price="4000"),
    ]
    s = portfolio_summary(items)
    assert s.total_value == Decimal("10000.00")
    p = next(p for p in s.positions if p.symbol == "AAPL")
    assert p.quantity == Decimal("10")
    assert p.cost == Decimal("5000.00")
    assert p.value == Decimal("6000.00")
    assert p.gain == Decimal("1000.00")
    assert p.gain_pct == Decimal("20.0")
    assert p.share_pct == Decimal("60.0")
    assert p.avg_price == Decimal("500.00")


def test_positions_lot_without_fx_rate_nulls_totals():
    items = [_lot(1, qty="2", price="100"), _lot(2, qty="3", price="50", currency="CHF")]
    p = portfolio_summary(items, {}).positions[0]
    assert p.quantity == Decimal("5")
    for f in ("cost", "value", "gain", "gain_pct", "share_pct", "avg_price"):
        assert getattr(p, f) is None
    chf = next(lot for lot in p.lots if lot.holding_id == 2)
    assert chf.currency == "CHF"
    assert chf.cost == Decimal("150.00") and chf.value == Decimal("150.00")


def test_positions_foreign_currency_lot():
    h = _lot(1, qty="5", price="150", currency="USD", market_price=Decimal("200"))
    lot = portfolio_summary([h], {"USD": Decimal("4")}).positions[0].lots[0]
    assert lot.currency == "USD"
    assert lot.cost == Decimal("750.00")
    assert lot.value == Decimal("1000.00")
    assert lot.value_source == "market"
    assert lot.gain == Decimal("250.00")
    assert lot.gain_pct == Decimal("33.3")


def test_positions_quote_in_other_currency_than_lot():
    h = _lot(1, qty="1", price="500", market_price=Decimal("200"), price_currency="USD")
    lot = portfolio_summary([h], {"USD": Decimal("4")}).positions[0].lots[0]
    assert lot.currency == "PLN"
    assert lot.value == Decimal("800.00")
    assert lot.cost == Decimal("500.00")


def test_positions_lot_order_undated_last():
    items = [
        _lot(1, purchase_date=date(2024, 9, 2)),
        _lot(2, purchase_date=None),
        _lot(3, purchase_date=date(2024, 3, 1)),
    ]
    lots = portfolio_summary(items).positions[0].lots
    assert [lot.holding_id for lot in lots] == [3, 1, 2]
