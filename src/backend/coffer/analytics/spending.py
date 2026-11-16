"""Spending statistics per category: pure functions, no database, no HTTP (amounts only)."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from coffer.analytics.compare import CategoryChange
from coffer.analytics.month import TxView
from coffer.core.money import ZERO, quantize

_PCT = Decimal("0.1")
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class CategoryStats:
    category_id: int
    category_name: str
    count: int
    total: Decimal
    average: Decimal
    largest: Decimal


@dataclass(frozen=True)
class TotalChange:
    current: Decimal
    previous: Decimal
    change: Decimal
    change_pct: Decimal | None


def category_stats(views: Iterable[TxView]) -> list[CategoryStats]:
    """Expense count, total, average and largest expense per category, largest total first."""
    amounts: dict[int, list[Decimal]] = {}
    names: dict[int, str] = {}
    for v in views:
        if v.base_amount < 0:
            amounts.setdefault(v.category_id, []).append(quantize(-v.base_amount))
            names[v.category_id] = v.category_name
    result = [
        CategoryStats(
            cid,
            names[cid],
            len(items),
            quantize(sum(items, ZERO)),
            quantize(sum(items, ZERO) / len(items)),
            max(items),
        )
        for cid, items in amounts.items()
    ]
    return sorted(result, key=lambda s: (-s.total, s.category_name))


def total_change(changes: Sequence[CategoryChange]) -> TotalChange:
    """Total expenses of the two compared months and the change between them."""
    current = quantize(sum((c.current for c in changes), ZERO))
    previous = quantize(sum((c.previous for c in changes), ZERO))
    change = quantize(current - previous)
    pct = None if previous == 0 else (change / previous * _HUNDRED).quantize(_PCT)
    return TotalChange(current, previous, change, pct)


def cut_savings(amount: Decimal, cut_pct: Decimal) -> tuple[Decimal, Decimal]:
    """Saving from cutting a monthly `amount` by `cut_pct`%: (per month, per year)."""
    monthly = quantize(amount * cut_pct / _HUNDRED)
    return monthly, quantize(monthly * 12)
