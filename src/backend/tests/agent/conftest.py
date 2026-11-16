import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from coffer.accounts.models import User
from coffer.agent.llm import get_llm_client
from coffer.main import app
from coffer.portfolio import service as portfolio_service
from coffer.portfolio.models import Holding
from coffer.profile.models import InvestmentProfile


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """LLM retries back off with time.sleep; record the delays instead of waiting."""
    delays: list[float] = []
    monkeypatch.setattr("coffer.agent.llm._sleep", delays.append)
    return delays


@pytest.fixture(autouse=True)
def no_market(monkeypatch: pytest.MonkeyPatch) -> None:
    """Portfolio valuation never reaches the network: no quotes, no FX rates."""
    monkeypatch.setattr(portfolio_service, "fetch_prices", lambda *args, **kwargs: None)
    monkeypatch.setattr(portfolio_service, "fetch_fx_rates", lambda *args, **kwargs: {})


@pytest.fixture
def use_llm():
    def _use(llm):
        app.dependency_overrides[get_llm_client] = lambda: llm
        return llm

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


@pytest.fixture
def add_holding(db: Session) -> Callable[..., Holding]:
    def _add(
        user: User,
        asset_class: str = "stock",
        value: str = "1000.00",
        name: str = "Tajna nazwa pozycji",
        symbol: str | None = None,
        note: str | None = "tajna notatka",
    ) -> Holding:
        h = Holding(
            user_id=user.id,
            name=name,
            symbol=symbol,
            asset_class=asset_class,
            quantity=Decimal("1"),
            purchase_price=Decimal(value),
            manual_value=Decimal(value),
            note=note,
        )
        db.add(h)
        db.commit()
        return h

    return _add


@pytest.fixture
def portfolio(user: User, add_holding) -> User:
    """50% stocks, 30% bonds, 20% cash of 10 000 PLN (stock share is a 'big position')."""
    add_holding(user, "stock", "5000.00", symbol="AAPL")
    add_holding(user, "bond", "3000.00")
    add_holding(user, "cash", "2000.00")
    return user


@pytest.fixture
def profile(db: Session, portfolio: User) -> InvestmentProfile:
    p = InvestmentProfile(
        user_id=portfolio.id, horizon="long", risk="high", preferred_classes=["stocks"]
    )
    db.add(p)
    db.commit()
    return p


def step(action: str, **kwargs: Any) -> str:
    return json.dumps({"action": action, **kwargs}, ensure_ascii=False)


def final(**overrides: Any) -> str:
    answer: dict[str, Any] = {
        "headline": "Portfel jest skoncentrowany w akcjach.",
        "findings": [
            {
                "title": "Struktura portfela",
                "detail": "Portfel wymaga uwagi.",
                "refers_to": "portfolio",
                "value": None,
            }
        ],
        "recommendations": [],
        "risks": ["Rynek akcji bywa zmienny."],
        "source_urls": [],
        **overrides,
    }
    return step("final", answer=answer)


@pytest.fixture(autouse=True)
def reset_action_guard() -> None:
    """The abuse guard is process-wide; every test starts with an empty budget."""
    from coffer.agent.guard import guard

    guard.reset()
