import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from coffer.accounts.models import AuthSession, User
from coffer.accounts.tokens import SESSION_COOKIE, hash_token, new_token
from coffer.core.config import get_settings
from coffer.core.db import get_db, get_session_factory
from coffer.main import app
from coffer.transactions.models import Category

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
                "investment_profiles, agent_runs, suggestions "
                "RESTART IDENTITY CASCADE"
            )
        )


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
