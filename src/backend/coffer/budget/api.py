from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Path

from coffer.accounts.deps import CurrentUser
from coffer.analytics.month import MonthSummary
from coffer.budget import service
from coffer.budget.schemas import (
    InsightsOut,
    MonthSummaryOut,
    NetWorthOut,
)
from coffer.core.clock import today
from coffer.core.db import DbSession
from coffer.core.months import MonthStr

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("/net-worth", response_model=NetWorthOut)
def get_net_worth(user: CurrentUser, db: DbSession) -> NetWorthOut:
    as_of = today()
    return NetWorthOut(**asdict(service.net_worth(db, user.id, as_of)), as_of=as_of)


@router.get("/{month}/insights", response_model=InsightsOut)
def get_insights(
    month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession
) -> service.MonthInsights:
    return service.month_insights(db, user.id, month)


@router.get("/{month}", response_model=MonthSummaryOut)
def get_month(month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession) -> MonthSummary:
    return service.month_summary(db, user.id, month)
