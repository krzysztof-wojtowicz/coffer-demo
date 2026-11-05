from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from coffer.core.money import ZERO, quantize
from coffer.core.months import parse_month


@dataclass(frozen=True)
class TxView:
    date: date
    base_amount: Decimal
    category_id: int
    category_name: str
    in_budget: bool


@dataclass(frozen=True)
class CategoryTotal:
    category_id: int
    category_name: str
    expenses: Decimal


@dataclass(frozen=True)
class MonthSummary:
    month: str
    income: Decimal
    expenses: Decimal
    balance: Decimal
    surplus: Decimal
    by_category: list[CategoryTotal]


def month_summary(month: str, txs: Iterable[TxView]) -> MonthSummary:
    start, end = parse_month(month)
    income = ZERO
    expenses = ZERO
    names: dict[int, str] = {}
    per_category: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for tx in txs:
        if not tx.in_budget or not (start <= tx.date < end):
            continue
        amount = quantize(tx.base_amount)
        if amount > 0:
            income += amount
        elif amount < 0:
            expenses += -amount
            names[tx.category_id] = tx.category_name
            per_category[tx.category_id] += -amount
    by_category = sorted(
        (
            CategoryTotal(cid, names[cid], quantize(total))
            for cid, total in per_category.items()
            if total > 0
        ),
        key=lambda c: (-c.expenses, c.category_name),
    )
    income = quantize(income)
    expenses = quantize(expenses)
    balance = quantize(income - expenses)
    return MonthSummary(
        month=month,
        income=income,
        expenses=expenses,
        balance=balance,
        surplus=max(balance, ZERO),
        by_category=by_category,
    )
