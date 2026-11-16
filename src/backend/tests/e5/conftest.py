"""Shared fixtures for the cross-cutting Stage 5 tests (written from E5-00 / E5-10)."""

import json
import socket
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from coffer.agent.guard import guard
from coffer.agent.llm import get_llm_client
from coffer.main import app
from coffer.market import service as market_service
from coffer.market.service import CompanyProfile, MarketTip, PriceHistory, Quote, SymbolMatch
from coffer.portfolio import service as portfolio_service
from coffer.portfolio.models import Holding
from coffer.profile.models import InvestmentProfile
from coffer.transactions.models import Category, Transaction
from tests.conftest import login_as

EMAIL = "anna.kowalska@example.com"
SECRET_TX = "SKLEP-SEKRET-123"
SECRET_HOLDING = "Konto u Jana"
SECRET_NOTE = "NOTATKA-TAJNA-777"
NOW = datetime(2025, 4, 10, 12, tzinfo=UTC)


def _prev_month() -> str:
    today = date.today()
    idx = today.year * 12 + today.month - 2
    return f"{idx // 12}-{idx % 12 + 1:02d}"


PREV_MONTH = _prev_month()

# (action id, params): every one of the 6 catalogue actions
ACTION_CASES: list[tuple[str, dict[str, Any]]] = [
    ("portfolio_review", {}),
    ("savings_analysis", {"month": PREV_MONTH, "months_back": 3}),
    ("purchase_impact", {"asset_class": "stock", "symbol": "AAPL", "amount": "1000.00"}),
    ("budget_plan", {}),
    ("investment_ideas", {"amount": "1500.00"}),
    ("company_research", {"query": "PKO BP"}),
]
REFERS = {
    "portfolio_review": "portfolio",
    "savings_analysis": "budget",
    "purchase_impact": "portfolio",
    "budget_plan": "budget",
    "investment_ideas": "market",
    "company_research": "market",
}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal", None, ""}


def final_answer(action: str, headline: str = "Podsumowanie bez liczb") -> str:
    return json.dumps(
        {
            "action": "final",
            "answer": {
                "headline": headline,
                "findings": [
                    {
                        "title": "Wniosek",
                        "detail": "Opis ogolny.",
                        "refers_to": REFERS[action],
                        "value": None,
                    }
                ],
                "recommendations": [],
                "risks": ["Rynek bywa zmienny."],
                "source_urls": [],
            },
        },
        ensure_ascii=False,
    )


@pytest.fixture(autouse=True)
def reset_guard():
    guard.reset()
    yield
    guard.reset()


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    monkeypatch.setattr("coffer.agent.llm._sleep", lambda _s: None, raising=False)


@pytest.fixture(autouse=True)
def network_attempts(monkeypatch) -> list[Any]:
    """Block outbound sockets (local DB connections are allowed); record the attempts."""
    attempts: list[Any] = []
    real_connect = socket.socket.connect
    real_gai = socket.getaddrinfo

    def connect(self, address):
        if isinstance(address, tuple) and address and address[0] not in LOCAL_HOSTS:
            if not str(address[0]).startswith("127."):
                attempts.append(address)
                raise OSError("network blocked in tests/e5")
        return real_connect(self, address)

    def gai(host, *args, **kwargs):
        if host not in LOCAL_HOSTS and not str(host).startswith("127."):
            attempts.append(host)
            raise OSError("network blocked in tests/e5")
        return real_gai(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", gai)
    return attempts


@pytest.fixture(autouse=True)
def market(monkeypatch):
    """market.service fully mocked: no quotes of its own, deterministic news/profile."""
    monkeypatch.setattr(portfolio_service, "fetch_prices", lambda *a, **k: None)
    monkeypatch.setattr(portfolio_service, "fetch_fx_rates", lambda *a, **k: {})
    ms = market_service
    monkeypatch.setattr(
        ms,
        "search_symbols",
        lambda q, limit=5: (
            [SymbolMatch("PKO.WA", "PKO Bank Polski", "WSE", "EQUITY")]
            if "PKO" in q.upper()
            else []
        ),
    )
    profile = CompanyProfile(
        "PKO.WA",
        "PKO Bank Polski",
        "Financial Services",
        "Banks",
        "PL",
        None,
        "Najwiekszy polski bank.",
        Decimal("70000000000"),
        Decimal("8.5"),
        Decimal("5.1"),
        "PLN",
        NOW,
        "https://finance.yahoo.com/quote/PKO.WA/profile",
    )
    monkeypatch.setattr(ms, "get_company_profile", lambda s: profile)
    monkeypatch.setattr(
        ms,
        "get_quotes",
        lambda symbols, db=None: {
            s: Quote(s, s, Decimal("55.50"), "PLN", None, NOW) for s in symbols
        },
    )
    tip = MarketTip("Wyniki rynku", "Skrot.", "Reuters", "https://example.com/rynek", NOW, NOW)
    monkeypatch.setattr(ms, "get_company_news", lambda s, limit=5: [tip])
    monkeypatch.setattr(ms, "get_market_tips", lambda limit=5: [tip])
    pts = [(date(2024, 4, 10), Decimal("50")), (date(2025, 4, 10), Decimal("55.5"))]
    monkeypatch.setattr(
        ms,
        "get_price_history",
        lambda s, p="1y": PriceHistory(s, "PLN", pts, NOW, "https://finance.yahoo.com/h"),
    )
    monkeypatch.setattr(ms, "get_wikipedia_summary", lambda q, lang="pl": None)
    monkeypatch.setattr(ms, "get_fx_rate", lambda a, b: Decimal("1"))


@pytest.fixture
def use_llm():
    def _use(llm):
        app.dependency_overrides[get_llm_client] = lambda: llm
        return llm

    yield _use
    app.dependency_overrides.pop(get_llm_client, None)


def _months_back(n: int) -> tuple[int, int]:
    today = date.today()
    idx = today.year * 12 + today.month - 1 - n
    return idx // 12, idx % 12 + 1


def seed_user(db, user, tag: str = "") -> None:
    """Transactions (unique descriptions), holdings with name+note, profile, for one user."""
    cats = {
        c.name: c.id
        for c in db.scalars(
            select(Category).where(Category.name.in_(["Wynagrodzenie", "Jedzenie"]))
        )
    }
    for back in (1, 2, 3):
        y, m = _months_back(back)
        for cat, amount, day in (("Wynagrodzenie", "6000.00", 2), ("Jedzenie", "-900.00", 9)):
            db.add(
                Transaction(
                    user_id=user.id,
                    date=date(y, m, day),
                    amount=Decimal(amount),
                    currency="PLN",
                    base_amount=Decimal(amount),
                    description=f"{SECRET_TX}{tag}",
                    category_id=cats[cat],
                    source="manual",
                )
            )
    for name, cls, sym, value, note in (
        (SECRET_HOLDING + tag, "cash", None, "3000.00", SECRET_NOTE + tag),
        ("Apple tajny" + tag, "stock", "AAPL", "5000.00", SECRET_NOTE + tag),
        ("Obligacje tajne" + tag, "bond", None, "2000.00", None),
    ):
        db.add(
            Holding(
                user_id=user.id,
                name=name,
                symbol=sym,
                asset_class=cls,
                quantity=Decimal("1"),
                purchase_price=Decimal(value),
                manual_value=Decimal(value),
                note=note,
            )
        )
    db.add(
        InvestmentProfile(
            user_id=user.id, horizon="long", risk="high", preferred_classes=["stocks"]
        )
    )
    db.commit()


@pytest.fixture
def anna(make_user, db):
    u = make_user(email=EMAIL)
    seed_user(db, u)
    return u


@pytest.fixture
def bob(make_user, db):
    u = make_user(email="bob.nowak@example.com")
    seed_user(db, u, tag="-BOB")
    return u


@pytest.fixture
def anna_client(anna) -> TestClient:
    c = login_as(TestClient(app), anna)
    cat = c.get("/api/budget/limits")
    assert cat.status_code == 200
    return c


@pytest.fixture
def bob_client(bob) -> TestClient:
    return login_as(TestClient(app), bob)


def run_action_api(client: TestClient, action: str, params: dict[str, Any] | None = None):
    return client.post(f"/api/agent/actions/{action}/run", json={"params": params or {}})
