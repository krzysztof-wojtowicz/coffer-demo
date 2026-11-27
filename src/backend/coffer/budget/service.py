import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from coffer.analytics.compare import CategoryChange, CategoryGrowth, compare_months, top_growth
from coffer.analytics.limits import LimitStatus, limit_status
from coffer.analytics.month import MonthSummary
from coffer.analytics.month import month_summary as compute_month_summary
from coffer.analytics.net_worth import NetWorth, cash_amounts, portfolio_is_complete
from coffer.analytics.net_worth import net_worth as compute_net_worth
from coffer.budget.models import BudgetLimit
from coffer.cash import service as cash_service
from coffer.core.months import parse_month
from coffer.portfolio import service as portfolio_service
from coffer.transactions.service import (
    UnknownCategoryError,
    get_category,
    list_categories,
    list_views,
)


class NotBudgetCategoryError(Exception):
    pass


@dataclass(frozen=True)
class LimitView:
    category_id: int
    category_name: str
    amount: Decimal


@dataclass(frozen=True)
class MonthInsights:
    month: str
    previous_month: str
    comparison: list[CategoryChange]
    top_growth: list[CategoryGrowth]
    limits: list[LimitStatus]


def month_summary(db: Session, user_id: int, month: str) -> MonthSummary:
    start, end = parse_month(month)
    return compute_month_summary(month, list_views(db, user_id, start, end))


def net_worth(db: Session, user_id: int, today: dt.date) -> NetWorth:
    """Cash counts ALL transactions (also out-of-budget categories), unlike the monthly budget."""
    views = list_views(db, user_id, dt.date.min, today + dt.timedelta(days=1))
    opening = cash_service.get(db, user_id)
    amounts = cash_amounts(
        [(v.date, v.amount) for v in views], today, opening.as_of if opening else None
    )
    result = portfolio_service.summary(db, user_id)
    return compute_net_worth(
        amounts,
        result.summary.total_value,
        portfolio_is_complete(result.summary, result.prices_available),
        opening.amount if opening else None,
    )


def _shift_month(month: str, delta: int) -> str:
    start, _ = parse_month(month)
    index = start.year * 12 + (start.month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def list_limits(db: Session, user_id: int) -> list[LimitView]:
    names = {c.id: c.name for c in list_categories(db)}
    rows = db.scalars(select(BudgetLimit).where(BudgetLimit.user_id == user_id))
    views = [LimitView(r.category_id, names[r.category_id], r.amount) for r in rows]
    return sorted(views, key=lambda v: v.category_name)


def set_limit(db: Session, user_id: int, category_id: int, amount: Decimal) -> LimitView:
    category = get_category(db, category_id)
    if category is None:
        raise UnknownCategoryError
    if not category.in_budget:
        raise NotBudgetCategoryError
    stmt = insert(BudgetLimit).values(user_id=user_id, category_id=category_id, amount=amount)
    db.execute(
        stmt.on_conflict_do_update(
            constraint="pk_budget_limits",
            set_={"amount": amount, "updated_at": func.now()},
        )
    )
    db.commit()
    return LimitView(category_id, category.name, amount)


def delete_limit(db: Session, user_id: int, category_id: int) -> bool:
    result = db.execute(
        delete(BudgetLimit).where(
            BudgetLimit.user_id == user_id, BudgetLimit.category_id == category_id
        )
    )
    db.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


def month_summaries(db: Session, user_id: int, month: str, count: int) -> list[MonthSummary]:
    """`month` and the `count - 1` months before it, newest first (one query)."""
    months = [_shift_month(month, -i) for i in range(count)]
    start, _ = parse_month(months[-1])
    _, end = parse_month(month)
    views = list_views(db, user_id, start, end)
    return [compute_month_summary(m, views) for m in months]


def month_insights(db: Session, user_id: int, month: str) -> MonthInsights:
    summaries = month_summaries(db, user_id, month, 4)
    current, previous, history = summaries[0], summaries[1], summaries[1:]
    limits = {v.category_id: (v.category_name, v.amount) for v in list_limits(db, user_id)}
    return MonthInsights(
        month=month,
        previous_month=previous.month,
        comparison=compare_months(current, previous),
        top_growth=top_growth(current, history),
        limits=limit_status(current.by_category, limits),
    )
