from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from coffer.analytics.market_stats import price_stats

D0 = date(2026, 1, 1)


def _series(prices):
    return [(D0 + timedelta(days=i), Decimal(p)) for i, p in enumerate(prices)]


def test_too_short_is_none():
    assert price_stats([]) is None
    assert price_stats(_series(["10"])) is None


def test_known_values():
    s = price_stats(_series(["100", "110", "99", "120"]))
    assert s is not None
    assert (s.first, s.last, s.min, s.max) == (
        Decimal(100),
        Decimal(120),
        Decimal(99),
        Decimal(120),
    )
    assert s.return_pct == Decimal("20.00")
    assert s.max_drawdown_pct == Decimal("-10.00")
    assert s.volatility_pct > 0


def test_flat_series_has_zero_risk():
    s = price_stats(_series(["5", "5", "5"]))
    assert s is not None
    assert s.volatility_pct == Decimal("0.00") and s.max_drawdown_pct == Decimal("0.00")


@given(st.lists(st.integers(1, 10**6), min_size=2, max_size=60))
def test_invariants(cents):
    s = price_stats(_series([Decimal(c) / 100 for c in cents]))
    assert s is not None
    assert s.min <= s.last <= s.max
    assert s.max_drawdown_pct <= 0
