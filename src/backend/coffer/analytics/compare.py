from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from coffer.analytics.month import MonthSummary
from coffer.core.money import ZERO, quantize

_PCT = Decimal("0.1")
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class CategoryChange:
    category_id: int
    category_name: str
    current: Decimal
    previous: Decimal
    change: Decimal
    change_pct: Decimal | None


@dataclass(frozen=True)
class CategoryGrowth:
    category_id: int
    category_name: str
    current: Decimal
    average_3m: Decimal
    increase: Decimal
    increase_pct: Decimal | None


def _pct(part: Decimal, base: Decimal) -> Decimal | None:
    if base == 0:
        return None
    return (part / base * _HUNDRED).quantize(_PCT, rounding=ROUND_HALF_UP)


def compare_months(current: MonthSummary, previous: MonthSummary) -> list[CategoryChange]:
    cur = {c.category_id: c for c in current.by_category}
    prev = {c.category_id: c for c in previous.by_category}
    result: list[CategoryChange] = []
    for cid in cur.keys() | prev.keys():
        name = (cur.get(cid) or prev[cid]).category_name
        cur_amount = cur[cid].expenses if cid in cur else ZERO
        prev_amount = prev[cid].expenses if cid in prev else ZERO
        change = quantize(cur_amount - prev_amount)
        result.append(
            CategoryChange(
                cid,
                name,
                cur_amount,
                prev_amount,
                change,
                _pct(change, prev_amount),
            )
        )
    return sorted(result, key=lambda c: (-abs(c.change), c.category_name))


def top_growth(
    current: MonthSummary, history: Sequence[MonthSummary], n: int = 3
) -> list[CategoryGrowth]:
    result: list[CategoryGrowth] = []
    for cat in current.by_category:
        if not cat.in_budget or not history:
            continue
        total = ZERO
        for month in history:
            total += next(
                (c.expenses for c in month.by_category if c.category_id == cat.category_id),
                ZERO,
            )
        average = quantize(total / len(history))
        increase = quantize(cat.expenses - average)
        if increase > 0:
            result.append(
                CategoryGrowth(
                    cat.category_id,
                    cat.category_name,
                    cat.expenses,
                    average,
                    increase,
                    _pct(increase, average),
                )
            )
    result.sort(key=lambda g: (-g.increase, g.category_name))
    return result[:n]
