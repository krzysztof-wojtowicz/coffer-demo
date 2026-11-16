from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from coffer.transactions.models import Category, Transaction


@pytest.fixture
def budget_cats(db):
    return list(
        db.scalars(select(Category).where(Category.in_budget.is_(True)).order_by(Category.id))
    )


@pytest.fixture
def non_budget_cat(db):
    return db.scalars(select(Category).where(Category.in_budget.is_(False)).limit(1)).first()


@pytest.fixture
def add_tx(db):
    def _add(user, day: date, amount: str, category_id: int, description: str = "x"):
        db.add(
            Transaction(
                user_id=user.id,
                date=day,
                amount=Decimal(amount),
                currency="PLN",
                base_amount=Decimal(amount),
                description=description,
                category_id=category_id,
                source="manual",
            )
        )
        db.commit()

    return _add
