from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.portfolio import (
    ClassAllocation,
    HoldingInput,
    gain_pct,
    portfolio_summary,
    value_holding,
)

D = Decimal


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


def test_gain_and_pct():
    s = portfolio_summary([h(market="110")])
    v = s.holdings[0]
    assert v.cost_basis == D("1000.00")
    assert v.current_value == D("1100.00")
    assert v.gain == D("100.00")
    assert v.gain_pct == D("10.0")
    assert v.share_pct == D("100.0")


def test_loss_is_negative():
    v = portfolio_summary([h(market="75")]).holdings[0]
    assert v.gain == D("-250.00")
    assert v.gain_pct == D("-25.0")


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
