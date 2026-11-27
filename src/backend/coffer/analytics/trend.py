from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from coffer.analytics.month import MonthSummary
from coffer.core.money import ZERO, quantize

_TENTH = Decimal("0.1")
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class MonthPoint:
    month: str
    income: Decimal
    expenses: Decimal
    balance: Decimal
    surplus: Decimal
    savings_rate: Decimal | None


@dataclass(frozen=True)
class Average:
    income: Decimal
    expenses: Decimal
    balance: Decimal
    surplus: Decimal
    savings_rate: Decimal | None


@dataclass(frozen=True)
class Change:
    amount: Decimal
    pct: Decimal | None


@dataclass(frozen=True)
class TrendChange:
    income: Change
    expenses: Change
    balance: Change
    surplus: Change
    savings_rate: Change | None  # amount in percentage points, pct always None


@dataclass(frozen=True)
class CategoryTrend:
    category_id: int
    category_name: str
    amounts: list[Decimal]
    average: Decimal | None
    change: Decimal | None
    change_pct: Decimal | None


@dataclass(frozen=True)
class Trend:
    month: str
    months: list[MonthPoint]
    average: Average | None
    change: TrendChange | None
    categories: list[CategoryTrend]


def _pct(part: Decimal, base: Decimal) -> Decimal | None:
    if base == 0:
        return None
    return (part / base * _HUNDRED).quantize(_TENTH, rounding=ROUND_HALF_UP)


def _change(current: Decimal, average: Decimal) -> Change:
    amount = quantize(current - average)
    return Change(amount, _pct(amount, average))


def _has_data(s: MonthSummary) -> bool:
    return s.income != 0 or s.expenses != 0


def trend(summaries: Sequence[MonthSummary]) -> Trend:
    """`summaries` oldest first; the last one is the selected month."""
    current = summaries[-1]
    earlier = [s for s in summaries[:-1] if _has_data(s)]
    n = len(earlier)

    points = [
        MonthPoint(
            s.month, s.income, s.expenses, s.balance, s.surplus, _pct(s.surplus, s.budget_income)
        )
        for s in summaries
    ]

    average: Average | None = None
    change: TrendChange | None = None
    if n:
        avg_income = quantize(sum((s.income for s in earlier), ZERO) / n)
        avg_expenses = quantize(sum((s.expenses for s in earlier), ZERO) / n)
        avg_balance = quantize(sum((s.balance for s in earlier), ZERO) / n)
        avg_surplus = quantize(sum((s.surplus for s in earlier), ZERO) / n)
        avg_budget_income = quantize(sum((s.budget_income for s in earlier), ZERO) / n)
        rate = _pct(avg_surplus, avg_budget_income)
        average = Average(avg_income, avg_expenses, avg_balance, avg_surplus, rate)
        current_rate = points[-1].savings_rate
        change = TrendChange(
            _change(current.income, avg_income),
            _change(current.expenses, avg_expenses),
            _change(current.balance, avg_balance),
            _change(current.surplus, avg_surplus),
            Change(current_rate - rate, None)
            if current_rate is not None and rate is not None
            else None,
        )

    per_month = [
        {c.category_id: c.expenses for c in s.by_category if c.in_budget} for s in summaries
    ]
    names = {
        c.category_id: c.category_name for s in summaries for c in s.by_category if c.in_budget
    }
    earlier_idx = [i for i, s in enumerate(summaries[:-1]) if _has_data(s)]
    categories: list[CategoryTrend] = []
    for cid, name in names.items():
        amounts = [m.get(cid, ZERO) for m in per_month]
        avg = quantize(sum((amounts[i] for i in earlier_idx), ZERO) / n) if n else None
        diff = quantize(amounts[-1] - avg) if avg is not None else None
        categories.append(
            CategoryTrend(
                cid,
                name,
                amounts,
                avg,
                diff,
                _pct(diff, avg) if diff is not None and avg is not None else None,
            )
        )
    categories.sort(key=lambda c: (-c.amounts[-1], -sum(c.amounts, ZERO), c.category_name))
    return Trend(current.month, points, average, change, categories)
