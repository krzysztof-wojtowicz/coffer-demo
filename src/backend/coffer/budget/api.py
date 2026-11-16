from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response

from coffer.accounts.deps import CurrentUser
from coffer.budget import service
from coffer.budget.schemas import (
    CategoryChangeOut,
    CategoryGrowthOut,
    InsightsOut,
    LimitIn,
    LimitOut,
    LimitStatusOut,
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
    n = service.net_worth(db, user.id, as_of)
    return NetWorthOut(
        cash_balance=f"{n.cash_balance:.2f}",
        portfolio_value=f"{n.portfolio_value:.2f}",
        net_worth=f"{n.net_worth:.2f}",
        portfolio_complete=n.portfolio_complete,
        opening_balance_set=n.opening_balance_set,
        as_of=as_of,
    )


@router.get("/limits", response_model=list[LimitOut])
def get_limits(user: CurrentUser, db: DbSession) -> list[LimitOut]:
    views = service.list_limits(db, user.id)
    return [LimitOut.build(v.category_id, v.category_name, v.amount) for v in views]


@router.put("/limits/{category_id}", response_model=LimitOut)
def put_limit(category_id: int, body: LimitIn, user: CurrentUser, db: DbSession) -> LimitOut:
    try:
        v = service.set_limit(db, user.id, category_id, body.amount)
    except UnknownCategoryError:
        raise HTTPException(status_code=404, detail="Nie znaleziono kategorii") from None
    except service.NotBudgetCategoryError:
        raise HTTPException(
            status_code=422, detail="Limit można ustawić tylko dla kategorii budżetowej"
        ) from None
    return LimitOut.build(v.category_id, v.category_name, v.amount)


@router.delete("/limits/{category_id}", status_code=204)
def delete_limit(category_id: int, user: CurrentUser, db: DbSession) -> Response:
    if not service.delete_limit(db, user.id, category_id):
        raise HTTPException(status_code=404, detail="Nie ustawiono limitu dla tej kategorii")
    return Response(status_code=204)


@router.get("/{month}/insights", response_model=InsightsOut)
def get_insights(
    month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession
) -> InsightsOut:
    i = service.month_insights(db, user.id, month)
    return InsightsOut(
        month=i.month,
        previous_month=i.previous_month,
        comparison=[CategoryChangeOut.from_change(c) for c in i.comparison],
        top_growth=[CategoryGrowthOut.from_growth(g) for g in i.top_growth],
        limits=[LimitStatusOut.from_status(s) for s in i.limits],
    )


@router.get("/{month}", response_model=MonthSummaryOut)
def get_month(
    month: Annotated[MonthStr, Path()], user: CurrentUser, db: DbSession
) -> MonthSummaryOut:
    return MonthSummaryOut.from_summary(service.month_summary(db, user.id, month))
