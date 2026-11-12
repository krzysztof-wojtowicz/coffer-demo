from fastapi import APIRouter, Response

from coffer.accounts.deps import CurrentUser
from coffer.cash import service
from coffer.cash.schemas import OpeningBalanceIn, OpeningBalanceOut
from coffer.core.db import DbSession

router = APIRouter(prefix="/api/cash", tags=["cash"])


@router.get("/opening-balance", response_model=OpeningBalanceOut | None)
def get_opening_balance(user: CurrentUser, db: DbSession) -> OpeningBalanceOut | None:
    row = service.get(db, user.id)
    return OpeningBalanceOut.model_validate(row) if row else None


@router.put("/opening-balance", response_model=OpeningBalanceOut)
def put_opening_balance(
    data: OpeningBalanceIn, user: CurrentUser, db: DbSession
) -> OpeningBalanceOut:
    return OpeningBalanceOut.model_validate(service.upsert(db, user.id, data))


@router.delete("/opening-balance", status_code=204)
def delete_opening_balance(user: CurrentUser, db: DbSession) -> Response:
    service.delete(db, user.id)
    return Response(status_code=204)
