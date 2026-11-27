from fastapi import APIRouter, HTTPException, Response

from coffer.accounts.deps import CurrentUser
from coffer.core.db import DbSession
from coffer.core.months import MonthStr
from coffer.transactions import service
from coffer.transactions.models import Category, Transaction
from coffer.transactions.schemas import (
    CategoryOut,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)

router = APIRouter(prefix="/api", tags=["transactions"])


@router.get("/categories", response_model=list[CategoryOut])
def get_categories(user: CurrentUser, db: DbSession) -> list[Category]:
    return service.list_categories(db)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionCreate, user: CurrentUser, db: DbSession) -> Transaction:
    try:
        tx = service.create(db, user.id, data)
    except service.UnknownCategoryError:
        raise HTTPException(status_code=422, detail="Nieznana kategoria") from None
    return tx


@router.get("/transactions", response_model=list[TransactionOut])
def get_transactions(
    user: CurrentUser, db: DbSession, month: MonthStr | None = None
) -> list[Transaction]:
    return service.list_for_user(db, user.id, month)


@router.patch("/transactions/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: int, data: TransactionUpdate, user: CurrentUser, db: DbSession
) -> Transaction:
    try:
        tx = service.update(db, user.id, transaction_id, data)
    except service.UnknownCategoryError:
        raise HTTPException(status_code=422, detail="Nieznana kategoria") from None
    if tx is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono transakcji")
    return tx


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> Response:
    if not service.delete(db, user.id, transaction_id):
        raise HTTPException(status_code=404, detail="Nie znaleziono transakcji")
    return Response(status_code=204)
