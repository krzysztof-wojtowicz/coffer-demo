from typing import Annotated

from fastapi import APIRouter, Path

from coffer.accounts.deps import CurrentUser
from coffer.budget import service
from coffer.budget.schemas import MonthSummaryOut
from coffer.core.db import DbSession
from coffer.core.months import MonthStr

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("/{month}", response_model=MonthSummaryOut)
def get_month(
    month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession
) -> MonthSummaryOut:
    return MonthSummaryOut.from_summary(service.month_summary(db, user.id, month))
