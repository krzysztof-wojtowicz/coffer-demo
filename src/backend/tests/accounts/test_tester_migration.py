"""Tester: migration 0005 (case-insensitive e-mails) on a dedicated scratch database."""

from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DB, TEST_URL

MIG_DB = f"{TEST_DB}_mig"


def _cfg(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture
def mig() -> Iterator[tuple[Config, Engine]]:
    admin = create_engine(TEST_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{MIG_DB}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{MIG_DB}"'))
    url = TEST_URL.set(database=MIG_DB)
    engine = create_engine(url)
    yield _cfg(url.render_as_string(hide_password=False)), engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{MIG_DB}" WITH (FORCE)'))
    admin.dispose()


def _version(engine: Engine) -> str:
    with engine.connect() as c:
        return c.scalar(text("SELECT version_num FROM alembic_version"))


def _emails(engine: Engine) -> list[str]:
    with engine.connect() as c:
        return list(c.scalars(text("SELECT email FROM users ORDER BY id")))


def _insert(engine: Engine, *emails: str) -> None:
    with engine.begin() as c:
        for e in emails:
            c.execute(text("INSERT INTO users (email, password_hash) VALUES (:e, 'x')"), {"e": e})


def test_duplicates_stop_upgrade_without_losing_accounts(mig) -> None:
    cfg, engine = mig
    command.upgrade(cfg, "0004")
    _insert(engine, "Jan@Example.com", "jan@example.com", " ola@example.com", "ola@example.com")
    with pytest.raises(RuntimeError, match="duplicates") as exc:
        command.upgrade(cfg, "head")
    assert "jan@example.com" in str(exc.value) and "ola@example.com" in str(exc.value)
    assert _version(engine) == "0004"
    assert len(_emails(engine)) == 4  # nothing deleted or renamed


def test_upgrade_normalizes_then_downgrade_upgrade_cycle(mig) -> None:
    cfg, engine = mig
    command.upgrade(cfg, "0004")
    _insert(engine, " Jan@Example.COM ", "ola@example.com")
    command.upgrade(cfg, "head")
    assert _emails(engine) == ["jan@example.com", "ola@example.com"]
    with pytest.raises(Exception, match="ux_users_email_lower"):
        _insert(engine, "OLA@example.com")

    command.downgrade(cfg, "0004")
    assert _version(engine) == "0004"
    with engine.connect() as c:
        cols = set(
            c.scalars(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
            )
        )
    assert "last_login_at" not in cols and "password_changed_at" not in cols
    with pytest.raises(Exception, match="users_email_key"):
        _insert(engine, "ola@example.com")

    command.upgrade(cfg, "head")
    assert _version(engine) == "0005"
    assert _emails(engine) == ["jan@example.com", "ola@example.com"]
