from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

TENTH = Decimal("0.1")
ZERO_PCT = Decimal("0.0")


def category_shares(by_category: Sequence[Any], total: Decimal) -> list[Decimal]:
    """Percentage share of each category in total, rounded half-up to 0.1.

    Items are Decimals or objects with an `expenses` Decimal attribute.
    """
    if total == 0:
        return [ZERO_PCT for _ in by_category]
    amounts = [getattr(c, "expenses", c) for c in by_category]
    return [(a * 100 / total).quantize(TENTH, rounding=ROUND_HALF_UP) for a in amounts]
