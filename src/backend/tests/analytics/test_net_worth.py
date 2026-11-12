from decimal import Decimal

from coffer.analytics.net_worth import net_worth, portfolio_is_complete
from coffer.analytics.portfolio import HoldingInput, portfolio_summary

D = Decimal


def test_sum_and_rounding():
    n = net_worth([D("100.005"), D("-30.00")], D("50.004"), True)
    assert (n.cash_balance, n.portfolio_value, n.net_worth) == (D("70.01"), D("50.00"), D("120.01"))
    assert n.portfolio_complete is True


def test_empty_is_zero():
    n = net_worth([], D("0"), True)
    assert n.net_worth == D("0.00")


def _h(**kw):
    base = dict(
        id=1, name="a", symbol="AAPL", asset_class="stock", quantity=D("1"), purchase_price=D("10")
    )
    return HoldingInput(**{**base, **kw})


def test_completeness():
    ok = portfolio_summary([_h(market_price=D("12"))])
    assert portfolio_is_complete(ok, True)
    no_price = portfolio_summary([_h()])
    assert not portfolio_is_complete(no_price, False)
    manual = portfolio_summary([_h(symbol=None)])
    assert portfolio_is_complete(manual, False)
    fx = portfolio_summary([_h(symbol=None, currency="USD")])
    assert not portfolio_is_complete(fx, True)
