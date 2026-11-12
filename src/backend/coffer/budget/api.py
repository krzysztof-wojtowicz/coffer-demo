from typing import Annotated

from fastapi import APIRouter, Path

from coffer.accounts.deps import CurrentUser
from coffer.budget import service
from coffer.budget.schemas import MonthSummaryOut, NetWorthOut
from coffer.core.clock import today
from coffer.core.db import DbSession
from coffer.core.months import MonthStr

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("/net-worth", response_model=NetWorthOut)
def get_net_worth(user: CurrentUser, db: DbSession) -> NetWorthOut:
    as_of = today()
    n = service.net_worth(db, user.id, as_of)
    return NetWorthOut(
        cash_balance=f"{n.cash_balance:.2f}",
        portfolio_value=f"{n.portfolio_value:.2f}",
        net_worth=f"{n.net_worth:.2f}",
        portfolio_complete=n.portfolio_complete,
        opening_balance_set=n.opening_balance_set,
        as_of=as_of,
    )


@router.get("/{month}", response_model=MonthSummaryOut)
def get_month(
    month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession
) -> MonthSummaryOut:
    return MonthSummaryOut.from_summary(service.month_summary(db, user.id, month))
