from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.accounts.models import User
from coffer.agent.tools.registry import ToolCall
from coffer.transactions.models import Category, Transaction

MONTH = "2025-03"
SECRET_DESC = "Przelew tajny Jan Kowalski"


@pytest.fixture
def add_tx(db: Session) -> Callable[..., Transaction]:
    def _add(
        user: User,
        amount: str,
        category: str = "Jedzenie",
        description: str = SECRET_DESC,
        day: int = 10,
        month: int = 3,
    ) -> Transaction:
        cat = db.scalars(select(Category).where(Category.name == category)).one()
        tx = Transaction(
            user_id=user.id,
            date=date(2025, month, day),
            amount=Decimal(amount),
            base_amount=Decimal(amount),
            description=description,
            category_id=cat.id,
            source="manual",
        )
        db.add(tx)
        db.commit()
        return tx

    return _add


def make_call(name: str, output: dict) -> ToolCall:
    return ToolCall(name=name, arguments={}, output=output, duration_ms=1)
