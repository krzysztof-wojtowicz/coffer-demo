from sqlalchemy.orm import Session

from coffer.analytics.month import MonthSummary
from coffer.analytics.month import month_summary as compute_month_summary
from coffer.core.months import parse_month
from coffer.transactions.service import list_views


def month_summary(db: Session, user_id: int, month: str) -> MonthSummary:
    start, end = parse_month(month)
    return compute_month_summary(month, list_views(db, user_id, start, end))
