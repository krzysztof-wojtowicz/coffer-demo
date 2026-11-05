from fastapi import APIRouter, HTTPException, Response

from coffer.accounts.deps import CurrentUser
from coffer.core.db import DbSession
from coffer.core.months import MonthStr
from coffer.transactions import service
from coffer.transactions.models import Category, Transaction
from coffer.transactions.schemas import CategoryOut, TransactionCreate, TransactionOut

router = APIRouter(prefix="/api", tags=["transactions"])


def _to_out(tx: Transaction, category_name: str) -> TransactionOut:
    return TransactionOut(
        id=tx.id,
        date=tx.date,
        amount=tx.amount,
        currency=tx.currency,
        description=tx.description,
        category_id=tx.category_id,
        category_name=category_name,
        source=tx.source,
    )


def _names(db: DbSession) -> dict[int, str]:
    return {c.id: c.name for c in service.list_categories(db)}


@router.get("/categories", response_model=list[CategoryOut])
def get_categories(user: CurrentUser, db: DbSession) -> list[Category]:
    return service.list_categories(db)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionCreate, user: CurrentUser, db: DbSession) -> TransactionOut:
    try:
        tx = service.create(db, user.id, data)
    except service.UnknownCategoryError:
        raise HTTPException(status_code=422, detail="Nieznana kategoria") from None
    return _to_out(tx, _names(db)[tx.category_id])


@router.get("/transactions", response_model=list[TransactionOut])
def get_transactions(
    user: CurrentUser, db: DbSession, month: MonthStr | None = None
) -> list[TransactionOut]:
    names = _names(db)
    return [_to_out(tx, names[tx.category_id]) for tx in service.list_for_user(db, user.id, month)]


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> Response:
    if not service.delete(db, user.id, transaction_id):
        raise HTTPException(status_code=404, detail="Nie znaleziono transakcji")
    return Response(status_code=204)
