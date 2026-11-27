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
    amount: Decimal
    category_id: int
    category_name: str
    in_budget: bool


@dataclass(frozen=True)
class CategoryTotal:
    category_id: int
    category_name: str
    expenses: Decimal
    in_budget: bool = True


@dataclass(frozen=True)
class MonthSummary:
    month: str
    income: Decimal
    expenses: Decimal
    balance: Decimal
    surplus: Decimal
    budget_income: Decimal  # positive in-budget amounts; base of the savings rate
    by_category: list[CategoryTotal]


def month_summary(month: str, txs: Iterable[TxView]) -> MonthSummary:
    start, end = parse_month(month)
    # income/expenses/balance/by_category cover ALL transactions (so months sum to cash);
    # surplus uses only in_budget categories (investing the surplus must not shrink it).
    income = ZERO
    expenses = ZERO
    budget_balance = ZERO
    budget_income = ZERO
    names: dict[int, str] = {}
    budget_flags: dict[int, bool] = {}
    per_category: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for tx in txs:
        if not (start <= tx.date < end):
            continue
        amount = quantize(tx.amount)
        if tx.in_budget:
            budget_balance += amount
            if amount > 0:
                budget_income += amount
        if amount > 0:
            income += amount
        elif amount < 0:
            expenses += -amount
            names[tx.category_id] = tx.category_name
            budget_flags[tx.category_id] = tx.in_budget
            per_category[tx.category_id] += -amount
    by_category = sorted(
        (
            CategoryTotal(cid, names[cid], quantize(total), budget_flags[cid])
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
        surplus=max(quantize(budget_balance), ZERO),
        budget_income=quantize(budget_income),
        by_category=by_category,
    )
