from sqlalchemy.orm import Session

from coffer.cash.models import OpeningBalance
from coffer.cash.schemas import OpeningBalanceIn


def get(db: Session, user_id: int) -> OpeningBalance | None:
    return db.get(OpeningBalance, user_id)


def upsert(db: Session, user_id: int, data: OpeningBalanceIn) -> OpeningBalance:
    row = db.get(OpeningBalance, user_id)
    if row is None:
        row = OpeningBalance(user_id=user_id)
        db.add(row)
    row.amount = data.amount
    row.as_of = data.as_of
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user_id: int) -> None:
    row = db.get(OpeningBalance, user_id)
    if row is not None:
        db.delete(row)
        db.commit()
