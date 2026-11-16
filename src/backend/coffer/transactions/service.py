import datetime as dt
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from coffer.analytics.month import TxView
from coffer.core.months import parse_month
from coffer.transactions.models import Category, Transaction
from coffer.transactions.schemas import TransactionCreate, TransactionUpdate


class UnknownCategoryError(Exception):
    pass


def get_category(db: Session, category_id: int) -> Category | None:
    return db.get(Category, category_id)


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)))


def create(db: Session, user_id: int, data: TransactionCreate) -> Transaction:
    if data.category_id is None:
        category = db.scalars(select(Category).where(Category.is_default.is_(True))).first()
    else:
        category = db.get(Category, data.category_id)
    if category is None:
        raise UnknownCategoryError
    tx = Transaction(
        user_id=user_id,
        date=data.date,
        amount=data.amount,
        currency="PLN",
        base_amount=data.amount,
        description=data.description,
        category_id=category.id,
        source="manual",
    )
    db.add(tx)
    db.commit()
    return tx


def update(
    db: Session, user_id: int, transaction_id: int, data: TransactionUpdate
) -> Transaction | None:
    tx = db.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    )
    if tx is None:
        return None
    if data.category_id is not None:
        if db.get(Category, data.category_id) is None:
            raise UnknownCategoryError
        tx.category_id = data.category_id
    if data.date is not None:
        tx.date = data.date
    if data.amount is not None:
        tx.amount = data.amount
        tx.base_amount = data.amount  # PLN only: base equals amount
    if data.description is not None:
        tx.description = data.description
    db.commit()
    return tx


@dataclass
class BulkItem:
    date: dt.date
    amount: Decimal
    description: str
    category_id: int
    needs_review: bool = False


def bulk_create(db: Session, user_id: int, items: list[BulkItem], source: str) -> int:
    """Dodaje transakcje (PLN) bez commitu; commit należy do wołającego."""
    for item in items:
        db.add(
            Transaction(
                user_id=user_id,
                date=item.date,
                amount=item.amount,
                currency="PLN",
                base_amount=item.amount,
                description=item.description[:500],
                category_id=item.category_id,
                source=source,
                needs_review=item.needs_review,
            )
        )
    db.flush()
    return len(items)


def list_for_user(db: Session, user_id: int, month: str | None) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user_id)
    if month is not None:
        start, end = parse_month(month)
        stmt = stmt.where(Transaction.date >= start, Transaction.date < end)
    stmt = stmt.order_by(Transaction.date.desc(), Transaction.id.desc())
    return list(db.scalars(stmt))


def delete(db: Session, user_id: int, transaction_id: int) -> bool:
    tx = db.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    )
    if tx is None:
        return False
    db.delete(tx)
    db.commit()
    return True


def list_views(db: Session, user_id: int, start: dt.date, end: dt.date) -> list[TxView]:
    rows = db.execute(
        select(Transaction, Category)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id, Transaction.date >= start, Transaction.date < end)
        .order_by(Transaction.date, Transaction.id)
    )
    return [
        TxView(
            date=tx.date,
            base_amount=tx.base_amount,
            category_id=cat.id,
            category_name=cat.name,
            in_budget=cat.in_budget,
        )
        for tx, cat in rows
    ]


def normalize_description(description: str) -> str:
    """Collapse whitespace and casefold: the shared key for dedup and category hints."""
    return " ".join(description.split()).casefold()


def dedup_keys(
    db: Session, user_id: int, start: dt.date, end: dt.date
) -> Counter[tuple[dt.date, Decimal, str]]:
    """Counts (date, amount, normalized description) of the user's transactions in [start, end)."""
    counter: Counter[tuple[dt.date, Decimal, str]] = Counter()
    rows = db.execute(
        select(Transaction.date, Transaction.amount, Transaction.description).where(
            Transaction.user_id == user_id, Transaction.date >= start, Transaction.date < end
        )
    )
    for d, amount, description in rows:
        counter[(d, amount, normalize_description(description))] += 1
    return counter


def category_hints(db: Session, user_id: int) -> dict[str, str]:
    """Normalized description -> category name of the user's newest non-review transaction."""
    key = func.lower(func.regexp_replace(func.trim(Transaction.description), r"\s+", " ", "g"))
    rows = db.execute(
        select(key, Category.name)
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id, Transaction.needs_review.is_(False))
        .ext(distinct_on(key))
        .order_by(key, Transaction.date.desc(), Transaction.id.desc())
    )
    return {normalize_description(description): name for description, name in rows}
