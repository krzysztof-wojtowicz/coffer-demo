from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response

from coffer.accounts.deps import CurrentUser
from coffer.analytics.month import MonthSummary
from coffer.budget import service
from coffer.budget.schemas import (
    InsightsOut,
    LimitIn,
    LimitOut,
    MonthSummaryOut,
    NetWorthOut,
)
from coffer.core.clock import today
from coffer.core.db import DbSession
from coffer.core.months import MonthStr
from coffer.transactions.service import UnknownCategoryError

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("/net-worth", response_model=NetWorthOut)
def get_net_worth(user: CurrentUser, db: DbSession) -> NetWorthOut:
    as_of = today()
    return NetWorthOut(**asdict(service.net_worth(db, user.id, as_of)), as_of=as_of)


@router.get("/limits", response_model=list[LimitOut])
def get_limits(user: CurrentUser, db: DbSession) -> list[service.LimitView]:
    return service.list_limits(db, user.id)


@router.put("/limits/{category_id}", response_model=LimitOut)
def put_limit(
    category_id: int, body: LimitIn, user: CurrentUser, db: DbSession
) -> service.LimitView:
    try:
        return service.set_limit(db, user.id, category_id, body.amount)
    except UnknownCategoryError:
        raise HTTPException(status_code=404, detail="Nie znaleziono kategorii") from None
    except service.NotBudgetCategoryError:
        raise HTTPException(
            status_code=422, detail="Limit można ustawić tylko dla kategorii budżetowej"
        ) from None


@router.delete("/limits/{category_id}", status_code=204)
def delete_limit(category_id: int, user: CurrentUser, db: DbSession) -> Response:
    if not service.delete_limit(db, user.id, category_id):
        raise HTTPException(status_code=404, detail="Nie ustawiono limitu dla tej kategorii")
    return Response(status_code=204)


@router.get("/{month}/insights", response_model=InsightsOut)
def get_insights(
    month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession
) -> service.MonthInsights:
    return service.month_insights(db, user.id, month)


@router.get("/{month}", response_model=MonthSummaryOut)
def get_month(month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession) -> MonthSummary:
    return service.month_summary(db, user.id, month)
