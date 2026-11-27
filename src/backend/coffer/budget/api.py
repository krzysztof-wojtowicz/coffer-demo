from dataclasses import asdict
from enum import IntEnum
from typing import Annotated

from fastapi import APIRouter, Path, Query

from coffer.accounts.deps import CurrentUser
from coffer.analytics.month import MonthSummary
from coffer.budget import service
from coffer.budget.schemas import (
    MonthSummaryOut,
    NetWorthOut,
    TrendOut,
)
from coffer.core.clock import today
from coffer.core.db import DbSession
from coffer.core.months import MonthStr


class TrendWindow(IntEnum):
    """IntEnum, not Literal: query strings are coerced to int only for enums."""

    three = 3
    six = 6
    twelve = 12


router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("/net-worth", response_model=NetWorthOut)
def get_net_worth(user: CurrentUser, db: DbSession) -> NetWorthOut:
    as_of = today()
    return NetWorthOut(**asdict(service.net_worth(db, user.id, as_of)), as_of=as_of)


@router.get("/{month}/trend", response_model=TrendOut)
def get_trend(
    month: Annotated[MonthStr, Path()],
    user: CurrentUser,
    db: DbSession,
    months: Annotated[TrendWindow, Query()] = TrendWindow.six,
) -> TrendOut:
    return TrendOut.model_validate(service.trend(db, user.id, month, int(months)))


@router.get("/{month}", response_model=MonthSummaryOut)
def get_month(month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession) -> MonthSummary:
    return service.month_summary(db, user.id, month)
