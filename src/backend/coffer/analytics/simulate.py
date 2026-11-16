"""What-if purchase on the portfolio allocation: pure functions, no database, no HTTP."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from coffer.analytics.allocation import TENTH
from coffer.core.money import ZERO, quantize


@dataclass(frozen=True)
class ClassValue:
    asset_class: str
    value: Decimal  # PLN


@dataclass(frozen=True)
class ClassShare:
    asset_class: str
    value: Decimal  # PLN
    share_pct: Decimal  # 0.1 precision; shares of one allocation sum to exactly 100


@dataclass(frozen=True)
class PurchaseImpact:
    before: list[ClassShare]
    after: list[ClassShare]
    total_before: Decimal
    total_after: Decimal
    new_class: bool  # the purchase opens an asset class the portfolio did not hold


def _shares(values: Mapping[str, Decimal]) -> list[ClassShare]:
    """Shares at 0.1 precision with the largest-remainder method, so they sum to 100.0."""
    total = sum(values.values(), ZERO)
    if total <= 0:
        return []
    units = {cls: v * 1000 / total for cls, v in values.items()}  # tenths of a percent
    floors = {cls: int(u) for cls, u in units.items()}
    missing = 1000 - sum(floors.values())
    by_remainder = sorted(units, key=lambda c: (floors[c] - units[c], c))
    for cls in by_remainder[:missing]:
        floors[cls] += 1
    shares = [ClassShare(cls, values[cls], Decimal(floors[cls]) * TENTH) for cls in values]
    return sorted(shares, key=lambda s: (-s.value, s.asset_class))


def simulate_purchase(
    classes: Sequence[ClassValue], asset_class: str, amount: Decimal
) -> PurchaseImpact:
    """Allocation before and after buying `amount` (PLN) of `asset_class`.

    An empty portfolio gives the bought class 100% (UC-07 3a). Raises ValueError for
    `amount <= 0`.
    """
    if amount <= 0:
        raise ValueError("Purchase amount must be positive")
    amount = quantize(amount)
    current: dict[str, Decimal] = {}
    for c in classes:
        if c.value > 0:
            current[c.asset_class] = current.get(c.asset_class, ZERO) + quantize(c.value)
    after = dict(current)
    after[asset_class] = after.get(asset_class, ZERO) + amount
    total_before = sum(current.values(), ZERO)
    return PurchaseImpact(
        before=_shares(current),
        after=_shares(after),
        total_before=quantize(total_before),
        total_after=quantize(total_before + amount),
        new_class=asset_class not in current,
    )


__all__ = ["ClassShare", "ClassValue", "PurchaseImpact", "simulate_purchase"]
