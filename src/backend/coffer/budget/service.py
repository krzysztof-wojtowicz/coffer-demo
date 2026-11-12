import datetime as dt

from sqlalchemy.orm import Session

from coffer.analytics.month import MonthSummary
from coffer.analytics.month import month_summary as compute_month_summary
from coffer.analytics.net_worth import NetWorth, cash_amounts, portfolio_is_complete
from coffer.analytics.net_worth import net_worth as compute_net_worth
from coffer.cash import service as cash_service
from coffer.core.months import parse_month
from coffer.portfolio import service as portfolio_service
from coffer.transactions.service import list_views


def month_summary(db: Session, user_id: int, month: str) -> MonthSummary:
    start, end = parse_month(month)
    return compute_month_summary(month, list_views(db, user_id, start, end))


def net_worth(db: Session, user_id: int, today: dt.date) -> NetWorth:
    """Cash counts ALL transactions (also out-of-budget categories), unlike the monthly budget."""
    views = list_views(db, user_id, dt.date.min, today + dt.timedelta(days=1))
    opening = cash_service.get(db, user_id)
    amounts = cash_amounts(
        [(v.date, v.base_amount) for v in views], today, opening.as_of if opening else None
    )
    result = portfolio_service.summary(db, user_id)
    return compute_net_worth(
        amounts,
        result.summary.total_value,
        portfolio_is_complete(result.summary, result.prices_available),
        opening.amount if opening else None,
    )
