from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Response

from coffer.accounts.deps import CurrentUser
from coffer.core.db import DbSession
from coffer.portfolio import service
from coffer.portfolio.schemas import (
    AllocationOut,
    HoldingCreate,
    HoldingOut,
    HoldingUpdate,
    HoldingValuationOut,
    PortfolioSummaryOut,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

NOT_FOUND = "Nie znaleziono pozycji portfela"


@router.get("/holdings", response_model=list[HoldingOut])
def list_holdings(user: CurrentUser, db: DbSession) -> list[HoldingOut]:
    return [HoldingOut.model_validate(h) for h in service.list_for_user(db, user.id)]


@router.post("/holdings", response_model=HoldingOut, status_code=201)
def create_holding(data: HoldingCreate, user: CurrentUser, db: DbSession) -> HoldingOut:
    return HoldingOut.model_validate(service.create(db, user.id, data))


@router.patch("/holdings/{holding_id}", response_model=HoldingOut)
def update_holding(
    holding_id: int, data: HoldingUpdate, user: CurrentUser, db: DbSession
) -> HoldingOut:
    holding = service.update(db, user.id, holding_id, data)
    if holding is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return HoldingOut.model_validate(holding)


@router.delete("/holdings/{holding_id}", status_code=204)
def delete_holding(holding_id: int, user: CurrentUser, db: DbSession) -> Response:
    if not service.delete(db, user.id, holding_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)


@router.get("/summary", response_model=PortfolioSummaryOut)
def get_summary(user: CurrentUser, db: DbSession) -> PortfolioSummaryOut:
    result = service.summary(db, user.id)
    s = result.summary
    return PortfolioSummaryOut(
        holdings=[
            HoldingValuationOut(**asdict(h), currency=result.currencies[h.id]) for h in s.holdings
        ],
        allocation=[AllocationOut(**asdict(a)) for a in s.allocation],
        total_value=s.total_value,
        total_cost=s.total_cost,
        total_gain=s.total_gain,
        total_gain_pct=s.total_gain_pct,
        prices_available=result.prices_available,
        fx_missing=s.fx_missing,
    )
