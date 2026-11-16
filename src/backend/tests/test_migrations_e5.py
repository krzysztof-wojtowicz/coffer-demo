"""Migrations 0007-0009: round trip, report backfill, CHECK and FK behaviour."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
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
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0006")
    with engine.connect() as conn:
        tables = set(
            conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        )
    assert not {"llm_usage_daily", "budget_limits", "market_quotes"} & tables
    command.upgrade(cfg, "head")
    command.check(cfg)


def test_backfill_report_and_downgrade(mig) -> None:
    cfg, engine = mig
    command.upgrade(cfg, "0006")
    rationale = [
        {"claim": "Nadwyżka 500", "refers_to": "budget", "value": "500.00"},
        {"claim": "Profil zrównoważony", "refers_to": "profile", "value": "balanced"},
    ]
    with engine.begin() as conn:
        uid = _user(conn)
        conn.execute(
            text(
                "INSERT INTO suggestions (user_id, type, month, summary, rationale, risks, "
                "sources, disclaimer, model, data_snapshot) VALUES (:u, 'surplus', '2026-10', "
                "'Podsumowanie', CAST(:r AS jsonb), '[\"ryzyko\"]', "
                "CAST(:s AS jsonb), 'Nie jest to porada', 'm', '{}')"
            ),
            {
                "u": uid,
                "r": json.dumps(rationale),
                "s": json.dumps([{"title": "A", "url": "https://a.example"}, {"title": "bez url"}]),
            },
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        report, source, status = conn.execute(
            text("SELECT report, source, ai_status FROM suggestions")
        ).one()
    assert report["headline"] == "Podsumowanie"
    assert len(report["findings"]) == 2
    assert report["findings"][0] == {
        "title": "Nadwyżka 500",
        "detail": "",
        "refers_to": "budget",
        "value": "500.00",
    }
    assert report["risks"] == ["ryzyko"]
    assert [s["url"] for s in report["sources"]] == ["https://a.example"]
    assert "fetched_at" in report["sources"][0]
    assert report["disclaimer"] == "Nie jest to porada"
    assert (source, status) == ("ai", "ok")

    command.downgrade(cfg, "0006")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM suggestions")) == 1


def _run_insert(conn, uid: int, status: str = "ok", provider: str | None = None):
    conn.execute(
        text(
            "INSERT INTO agent_runs (user_id, task, prompt_version, status, provider) "
            "VALUES (:u, 't', 'v', :s, :p)"
        ),
        {"u": uid, "s": status, "p": provider},
    )


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
        _run_insert(conn, uid, "timeout", "ollama")  # valid

    bad = [
        lambda c: _run_insert(c, uid, "bogus"),
        lambda c: _run_insert(c, uid, "ok", "bogus"),
        lambda c: c.execute(
            text(
                "INSERT INTO suggestions (user_id, type, summary, report, disclaimer, model, "
                "data_snapshot, source) VALUES (:u, 'x', 's', '{}', 'd', 'm', '{}', 'bogus')"
            ),
            {"u": uid},
        ),
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
        lambda c: c.execute(
            text("INSERT INTO llm_usage_daily (user_id, day, runs) VALUES (:u, '2026-11-16', -1)"),
            {"u": uid},
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
        conn.execute(
            text("INSERT INTO llm_usage_daily (user_id, day, runs) VALUES (:u, '2026-11-16', 1)"),
            {"u": uid},
        )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM categories WHERE id = :c"), {"c": cat})
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})
        assert conn.scalar(text("SELECT count(*) FROM budget_limits")) == 0
        assert conn.scalar(text("SELECT count(*) FROM llm_usage_daily")) == 0
