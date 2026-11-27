import datetime as dt
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yfinance
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from coffer.accounts.models import AuthSession, User
from coffer.accounts.ratelimit import limiter
from coffer.accounts.tokens import SESSION_COOKIE, hash_token, new_token
from coffer.core.config import get_settings
from coffer.core.db import get_db, get_session_factory
from coffer.main import app
from coffer.market import service as market
from coffer.transactions.models import Category, Transaction

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB = os.environ.get("COFFER_TEST_DB", "coffer_test")
TEST_URL = make_url(get_settings().database_url).set(database=TEST_DB)
_hasher = PasswordHasher()


@pytest.fixture(scope="session")
def test_engine():
    admin = create_engine(TEST_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin.dispose()

    url = TEST_URL.render_as_string(hide_password=False)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")

    engine = create_engine(TEST_URL)

    def override_get_db() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    test_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.dependency_overrides[get_session_factory] = lambda: test_factory
    yield engine
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_db(test_engine) -> Iterator[None]:
    yield
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, auth_sessions, transactions, import_drafts, "
                "investment_profiles, market_quotes "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def db(test_engine) -> Iterator[Session]:
    with Session(test_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def client(test_engine) -> TestClient:
    return TestClient(app)


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def _make(email: str = "user@example.com", password: str = "haslo12345") -> User:
        user = User(email=email.lower(), password_hash=_hasher.hash(password))
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def user(make_user: Callable[..., User]) -> User:
    return make_user()


def login_as(client: TestClient, user: User) -> TestClient:
    token = new_token()
    with Session(create_engine(TEST_URL)) as session:
        session.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.commit()
    client.cookies.set(SESSION_COOKIE, token)
    return client


@pytest.fixture
def auth_client(client: TestClient, user: User) -> TestClient:
    return login_as(client, user)


@pytest.fixture
def other_auth_client(make_user: Callable[..., User]) -> TestClient:
    other = make_user(email="other@example.com")
    return login_as(TestClient(app), other)


@pytest.fixture
def category_id(db: Session) -> Callable[[str], int]:
    def _get(name: str) -> int:
        return db.scalars(select(Category.id).where(Category.name == name)).one()

    return _get


def add_tx(db: Session, user: User, day, amount: str, category_id: int) -> None:
    db.add(
        Transaction(
            user_id=user.id,
            date=day,
            amount=Decimal(amount),
            description="x",
            category_id=category_id,
            source="manual",
        )
    )
    db.commit()


@dataclass
class Quote:
    symbol: str
    price: Decimal
    currency: str
    change_pct: Decimal | None
    as_of: dt.datetime


def fake_market(monkeypatch, prices=None, fail=False, fx=None):
    """Replace the market service (no network).

    prices: symbol -> "price" (PLN) or ("price", "CCY"); fx: CCY -> PLN rate (without `fx` no
    foreign rate is known). Returns the list of symbol lists requested.
    """
    calls: list[list[str]] = []

    def get_quotes(symbols, db=None):
        calls.append(list(symbols))
        if fail:
            raise market.MarketDataUnavailable("down")
        now = dt.datetime.now(dt.UTC)
        out = {}
        for s, p in (prices or {}).items():
            price, ccy = p if isinstance(p, tuple) else (p, "PLN")
            if s in symbols:
                out[s] = Quote(s, Decimal(price), ccy, None, now)
        return out

    def get_fx_quote(from_ccy, to_ccy, db=None):
        assert to_ccy == "PLN"
        rate = Decimal("1") if from_ccy == to_ccy else (fx or {}).get(from_ccy)
        return None if rate is None else (rate, dt.datetime.now(dt.UTC))

    monkeypatch.setattr(market, "get_quotes", get_quotes)
    monkeypatch.setattr(market, "get_fx_quote", get_fx_quote)
    return calls


PRICES: dict[str, dict[str, Any]] = {
    "AAPL": {"lastPrice": 190.125, "previousClose": 185.0, "currency": "USD"},
    "MSFT": {"lastPrice": 410.0, "previousClose": 0.0, "currency": "USD"},
    "PKO.WA": {"lastPrice": 55.555, "previousClose": 50.0, "currency": "pln"},
}


class FakeYF:
    def __init__(self) -> None:
        self.prices = dict(PRICES)
        self.fail: Exception | None = None
        self.fail_symbols: dict[str, Exception] = {}
        self.quote_calls: list[str] = []
        self.reachable = True

    def ticker(self, symbol: str) -> Any:
        fake = self

        class _Ticker:
            @property
            def fast_info(self) -> Any:
                fake.quote_calls.append(symbol)
                if fake.fail is not None:
                    raise fake.fail
                if symbol in fake.fail_symbols:
                    raise fake.fail_symbols[symbol]
                if symbol not in fake.prices:
                    raise KeyError("currentTradingPeriod")
                return fake.prices[symbol]

        return _Ticker()


@pytest.fixture
def fake_yf(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeYF]:
    fake = FakeYF()
    monkeypatch.setattr(yfinance, "Ticker", fake.ticker)
    monkeypatch.setattr(market, "_source_reachable", lambda: fake.reachable)
    market.clear_cache()
    yield fake
    market.clear_cache()
