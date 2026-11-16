from decimal import Decimal

from coffer.analytics.limits import limit_status
from coffer.analytics.month import CategoryTotal


def test_limit_status():
    spent = [CategoryTotal(1, "A", Decimal("150.00"))]
    limits = {1: ("A", Decimal("100.00")), 2: ("B", Decimal("50.00"))}
    a, b = limit_status(spent, limits)
    assert a.exceeded and a.remaining == Decimal("-50.00") and a.used_pct == Decimal("150.0")
    assert not b.exceeded and b.spent == Decimal("0.00") and b.used_pct == Decimal("0.0")


def test_exactly_at_limit_not_exceeded():
    [s] = limit_status([CategoryTotal(1, "A", Decimal("100.00"))], {1: ("A", Decimal("100.00"))})
    assert not s.exceeded


def test_used_pct_rounds_half_up():
    [s] = limit_status([CategoryTotal(1, "A", Decimal("12.25"))], {1: ("A", Decimal("100.00"))})
    assert s.used_pct == Decimal("12.3")
