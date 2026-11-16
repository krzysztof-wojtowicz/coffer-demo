"""Target asset allocation and gaps: pure functions, no database, no HTTP.

Classes are the portfolio holding classes (`stock`, `etf`, `bond`, `real_estate`, `commodity`,
`crypto`, `cash`). Percentages are Decimals rounded half-up to 0.1.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from coffer.core.money import ZERO

TENTH = Decimal("0.1")
HUNDRED = Decimal(100)

# Base split by risk tolerance (sums to 100).
_BASE: dict[str, dict[str, int]] = {
    "low": {"cash": 30, "bond": 50, "etf": 15, "stock": 5},
    "medium": {"cash": 15, "bond": 30, "etf": 30, "stock": 20, "real_estate": 5},
    "high": {"cash": 5, "bond": 10, "etf": 35, "stock": 40, "crypto": 5, "real_estate": 5},
}
# Horizon adjustment, in percentage points moved from the first classes of `take` (as far as
# they have anything) to `give`: a short horizon protects capital, a long one buys growth.
_SHIFT: dict[str, tuple[tuple[str, ...], str, int]] = {
    "short": (("crypto", "stock", "etf"), "cash", 15),
    "long": (("cash", "bond"), "etf", 10),
}

RISKS = tuple(_BASE)
HORIZONS = ("short", "medium", "long")


@dataclass(frozen=True)
class ClassGap:
    asset_class: str
    current_pct: Decimal
    target_pct: Decimal
    gap_pp: Decimal  # target - current; positive = underweight


def target_allocation(risk: str, horizon: str) -> dict[str, Decimal]:
    """Target share (%) per asset class for a risk tolerance and investment horizon.

    Rules: start from the base split for `risk` (low: 30 cash/50 bonds/15 ETF/5 stocks; medium:
    15/30/30/20 plus 5 real estate; high: 5/10/35/40 plus 5 crypto and 5 real estate). A short
    horizon moves 15 p.p. into cash (taken from crypto, then stocks, then ETF); a long horizon
    moves 10 p.p. into ETF (taken from cash, then bonds); medium leaves the base split. The
    result always sums to 100. Raises ValueError for unknown `risk` or `horizon`.
    """
    if risk not in _BASE or horizon not in HORIZONS:
        raise ValueError(f"Unknown risk/horizon: {risk}/{horizon}")
    weights = dict(_BASE[risk])
    if horizon in _SHIFT:
        take, give, points = _SHIFT[horizon]
        for cls in take:
            moved = min(points, weights.get(cls, 0))
            if moved:
                weights[cls] -= moved
                weights[give] = weights.get(give, 0) + moved
                points -= moved
        weights = {k: v for k, v in weights.items() if v}
    return {cls: Decimal(v).quantize(TENTH) for cls, v in weights.items()}


def share_pct(part: Decimal, total: Decimal) -> Decimal | None:
    """`part` as % of `total`, 0.1 precision half-up; None when total is not positive."""
    if total <= 0:
        return None
    return (part * HUNDRED / total).quantize(TENTH, rounding=ROUND_HALF_UP)


def allocation_gap(current: Mapping[str, Decimal], target: Mapping[str, Decimal]) -> list[ClassGap]:
    """Gap per class present in either mapping, largest absolute gap first (then by class)."""
    gaps = [
        ClassGap(
            asset_class=cls,
            current_pct=current.get(cls, ZERO),
            target_pct=target.get(cls, ZERO),
            gap_pp=target.get(cls, ZERO) - current.get(cls, ZERO),
        )
        for cls in set(current) | set(target)
    ]
    return sorted(gaps, key=lambda g: (-abs(g.gap_pp), g.asset_class))


def max_position_share(values: Sequence[Decimal]) -> Decimal | None:
    """Share (%) of the largest value in the sum of all values; None when there is no value."""
    if not values:
        return None
    return share_pct(max(values), sum(values, ZERO))
