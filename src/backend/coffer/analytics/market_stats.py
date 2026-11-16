import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from coffer.core.money import ZERO, quantize

TRADING_DAYS = 252


@dataclass(frozen=True)
class PriceStats:
    first: Decimal
    last: Decimal
    min: Decimal
    max: Decimal
    return_pct: Decimal
    volatility_pct: Decimal
    max_drawdown_pct: Decimal


def price_stats(points: Sequence[tuple[date, Decimal]]) -> PriceStats | None:
    """Return, annualised volatility (stdev of daily returns x sqrt(252)) and max drawdown.

    Needs at least 2 points with positive prices; otherwise None. Percentages have 2 places.
    """
    prices = [p for _, p in sorted(points, key=lambda x: x[0])]
    if len(prices) < 2 or any(p <= 0 for p in prices):
        return None
    returns = [float(b / a - 1) for a, b in zip(prices, prices[1:], strict=False)]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1) if len(returns) > 1 else 0
    volatility = Decimal(str(math.sqrt(variance) * math.sqrt(TRADING_DAYS) * 100))
    peak = prices[0]
    drawdown = ZERO
    for price in prices:
        peak = max(peak, price)
        drawdown = min(drawdown, (price - peak) / peak * 100)
    return PriceStats(
        first=prices[0],
        last=prices[-1],
        min=min(prices),
        max=max(prices),
        return_pct=quantize((prices[-1] - prices[0]) / prices[0] * 100),
        volatility_pct=quantize(volatility),
        max_drawdown_pct=quantize(drawdown),
    )
