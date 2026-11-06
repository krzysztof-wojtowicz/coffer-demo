import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from coffer.accounts.models import User
from coffer.transactions.models import Category, Transaction

MONTH = "2025-03"


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """LLM retries back off with time.sleep; record the delays instead of waiting."""
    delays: list[float] = []
    monkeypatch.setattr("coffer.agent.llm._sleep", delays.append)
    return delays


DESCRIPTION = "Przelew Jan Kowalski PL61109010140000071219812874"


@pytest.fixture
def budget_category(db: Session) -> Category:
    return db.scalars(
        select(Category).where(Category.in_budget.is_(True)).order_by(Category.id).limit(1)
    ).one()


@pytest.fixture
def add_tx(db: Session, budget_category: Category) -> Callable[..., Transaction]:
    def _add(user: User, amount: str, description: str = "opis", day: int = 10) -> Transaction:
        tx = Transaction(
            user_id=user.id,
            date=date(2025, 3, day),
            amount=Decimal(amount),
            currency="PLN",
            base_amount=Decimal(amount),
            description=description,
            category_id=budget_category.id,
            source="manual",
        )
        db.add(tx)
        db.commit()
        return tx

    return _add


@pytest.fixture
def surplus_data(user: User, add_tx) -> User:
    add_tx(user, "5000.00", "Wyplata firma")
    add_tx(user, "-1234.56", DESCRIPTION)
    return user


GOOD = json.dumps({"summary": "Odloz nadwyzke.", "rationale": ["Nadwyzka to 3765.44 PLN."]})
