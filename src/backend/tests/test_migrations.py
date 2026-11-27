"""Migrations: round trip, single head, CHECK and FK behaviour, e-mail normalization (0005)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DB, TEST_URL

DB = f"{TEST_DB}_mig"


def _cfg(url: str) -> Config:
    cfg = Config(str(Path(BACKEND_DIR) / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture
def mig() -> Iterator[tuple[Config, Engine]]:
    """A dedicated, freshly created database so the shared test DB is untouched."""
    admin = create_engine(TEST_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{DB}"'))
    url = TEST_URL.set(database=DB)
    engine = create_engine(url)
    cfg = _cfg(url.render_as_string(hide_password=False))
    yield cfg, engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)'))
    admin.dispose()


def _user(conn, email: str = "u@example.com") -> int:
    return conn.scalar(
        text("INSERT INTO users (email, password_hash) VALUES (:e, 'x') RETURNING id"), {"e": email}
    )


def test_round_trip(mig) -> None:
    cfg, engine = mig
    agent_tables = {"agent_runs", "suggestions", "llm_usage_daily"}

    def tables() -> set[str]:
        with engine.connect() as conn:
            return set(
                conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            )

    command.upgrade(cfg, "head")
    assert not agent_tables & tables()
    command.downgrade(cfg, "0009")
    assert agent_tables <= tables()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0006")
    assert not {"llm_usage_daily", "budget_limits", "market_quotes"} & tables()
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "base")
    assert tables() <= {"alembic_version"}
    command.upgrade(cfg, "head")


def test_single_head() -> None:
    assert len(ScriptDirectory.from_config(_cfg(TEST_URL.render_as_string())).get_heads()) == 1


def test_checks(mig) -> None:
    cfg, engine = mig
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        uid = _user(conn)
        cat = conn.scalar(
            text(
                "INSERT INTO categories (name, in_budget, is_default) "
                "VALUES ('Test', true, false) RETURNING id"
            )
        )
    bad = [
        lambda c: c.execute(
            text("INSERT INTO budget_limits (user_id, category_id, amount) VALUES (:u, :c, 0)"),
            {"u": uid, "c": cat},
        ),
        lambda c: c.execute(
            text(
                "INSERT INTO market_quotes (symbol, quote_date, price, currency, fetched_at) "
                "VALUES ('X', '2026-11-16', 0, 'PLN', now())"
            )
        ),
    ]
    for stmt in bad:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            stmt(conn)


def test_cascade_and_restrict(mig) -> None:
    cfg, engine = mig
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        uid = _user(conn)
        cat = conn.scalar(
            text(
                "INSERT INTO categories (name, in_budget, is_default) "
                "VALUES ('Test', true, false) RETURNING id"
            )
        )
        conn.execute(
            text("INSERT INTO budget_limits (user_id, category_id, amount) VALUES (:u, :c, 10)"),
            {"u": uid, "c": cat},
        )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM categories WHERE id = :c"), {"c": cat})
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})
        assert conn.scalar(text("SELECT count(*) FROM budget_limits")) == 0


# --- 0005: case-insensitive e-mails ---


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
    command.upgrade(cfg, "0005")
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

    command.upgrade(cfg, "0005")
    assert _version(engine) == "0005"
    assert _emails(engine) == ["jan@example.com", "ola@example.com"]


def test_every_fk_to_users_cascades(db) -> None:
    rows = db.execute(
        text(
            "SELECT c.conrelid::regclass::text, c.confdeltype FROM pg_constraint c "
            "WHERE c.contype = 'f' AND c.confrelid = 'users'::regclass"
        )
    ).all()
    assert rows
    assert {table for table, action in rows if action != "c"} == set()
