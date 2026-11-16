"""Savings and budget planning: pure functions, no database, no HTTP.

Money is rounded with `quantize` (half-up, 2 places). Rates are annual percentages; interest
compounds monthly and contributions are paid at the end of each month.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from coffer.analytics.month import MonthSummary
from coffer.core.money import ZERO, quantize

_TEN = Decimal(10)
_HUNDRED = Decimal(100)
_TWELVE = Decimal(12)


@dataclass(frozen=True)
class YearBalance:
    year: int
    balance: Decimal
    contributed: Decimal


@dataclass(frozen=True)
class GrowthResult:
    final_value: Decimal
    contributed: Decimal  # principal + all monthly payments
    interest: Decimal
    yearly: list[YearBalance]


@dataclass(frozen=True)
class ProposedLimit:
    category_id: int
    category_name: str
    average: Decimal
    proposed: Decimal


def compound_growth(
    principal: Decimal, monthly: Decimal, annual_rate_pct: Decimal, years: int
) -> GrowthResult:
    """Value after `years` of saving `monthly` on top of `principal` (monthly compounding)."""
    if principal < 0 or monthly < 0 or annual_rate_pct < 0 or years < 0:
        raise ValueError("Growth inputs must not be negative")
    rate = annual_rate_pct / _HUNDRED / _TWELVE
    balance = principal
    yearly: list[YearBalance] = []
    for month in range(1, years * 12 + 1):
        balance = balance * (1 + rate) + monthly
        if month % 12 == 0:
            yearly.append(
                YearBalance(month // 12, quantize(balance), quantize(principal + monthly * month))
            )
    contributed = quantize(principal + monthly * years * 12)
    final = quantize(balance)
    return GrowthResult(final, contributed, quantize(final - contributed), yearly)


def monthly_saving_for_goal(
    target: Decimal, current: Decimal, months: int, annual_rate_pct: Decimal = ZERO
) -> Decimal:
    """Monthly payment that takes `current` to `target` in `months` (0 when already there)."""
    if months <= 0:
        raise ValueError("Months must be positive")
    if annual_rate_pct < 0:
        raise ValueError("Rate must not be negative")
    if target <= current:
        return ZERO
    rate = annual_rate_pct / _HUNDRED / _TWELVE
    if rate == 0:
        return quantize((target - current) / months)
    growth = (1 + rate) ** months
    payment = (target - current * growth) * rate / (growth - 1)
    return quantize(max(payment, ZERO))


def average_by_category(
    summaries: Sequence[MonthSummary], budget_only: bool = True
) -> dict[int, tuple[str, Decimal]]:
    """Average monthly expenses per category over `summaries` (months without it count as 0)."""
    if not summaries:
        return {}
    totals: dict[int, Decimal] = {}
    names: dict[int, str] = {}
    for s in summaries:
        for c in s.by_category:
            if budget_only and not c.in_budget:
                continue
            totals[c.category_id] = totals.get(c.category_id, ZERO) + c.expenses
            names[c.category_id] = c.category_name
    return {cid: (names[cid], quantize(t / len(summaries))) for cid, t in totals.items()}


def average_totals(summaries: Sequence[MonthSummary]) -> tuple[Decimal, Decimal, Decimal]:
    """Average monthly (income, expenses, surplus)."""
    if not summaries:
        return ZERO, ZERO, ZERO
    n = len(summaries)
    return (
        quantize(sum((s.income for s in summaries), ZERO) / n),
        quantize(sum((s.expenses for s in summaries), ZERO) / n),
        quantize(sum((s.surplus for s in summaries), ZERO) / n),
    )


def _ceil_to_ten(value: Decimal) -> Decimal:
    return Decimal(math.ceil(value / _TEN) * 10).quantize(ZERO)


def propose_limits(
    averages: Mapping[int, tuple[str, Decimal]], growth_ids: set[int], cut_pct: Decimal
) -> list[ProposedLimit]:
    """Limit = average; categories in `growth_ids` get `cut_pct`% off. Rounded up to 10 zł."""
    if not 0 <= cut_pct <= 100:
        raise ValueError("cut_pct must be between 0 and 100")
    result = []
    for cid, (name, average) in averages.items():
        base = average * (1 - cut_pct / _HUNDRED) if cid in growth_ids else average
        result.append(ProposedLimit(cid, name, average, _ceil_to_ten(base)))
    return sorted(result, key=lambda p: (-p.average, p.category_name))


def previous_month(today: date) -> str:
    """The last full calendar month before `today` as YYYY-MM."""
    index = today.year * 12 + today.month - 2
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def shift_month(month: str, delta: int) -> str:
    """`month` (YYYY-MM) moved by `delta` months."""
    year, mon = int(month[:4]), int(month[5:7])
    index = year * 12 + mon - 1 + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"
