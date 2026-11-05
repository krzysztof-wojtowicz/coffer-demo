"""Database URL normalization (no network: only strings and engine construction)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from coffer.core.config import Settings
from coffer.core.db_url import engine_options, is_pooled_host, normalize_database_url

NEON = (
    "postgresql://alex:AbC123dEf@ep-cool-darkness-123456.eu-central-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)
NEON_POOLED = NEON.replace("123456.eu", "123456-pooler.eu")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (NEON, "postgresql+psycopg://" + NEON.removeprefix("postgresql://")),
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("POSTGRESQL://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("  postgres://u:p@h/db\n", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://coffer:coffer@localhost:5432/coffer", None),
        ("postgresql+psycopg2://u:p@h/db", None),
        ("sqlite:///x.db", None),
    ],
)
def test_normalize_database_url(raw: str, expected: str | None) -> None:
    assert normalize_database_url(raw) == (expected or raw.strip())


def test_normalize_keeps_ssl_params_and_credentials() -> None:
    url = make_url(normalize_database_url(NEON))
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "alex"
    assert url.password == "AbC123dEf"
    assert url.database == "neondb"
    assert url.query == {"sslmode": "require", "channel_binding": "require"}


def test_normalize_keeps_url_encoded_password() -> None:
    url = make_url(normalize_database_url("postgres://u:p%40ss%2Fw@h/db"))
    assert url.password == "p@ss/w"


def test_settings_normalize_database_url() -> None:
    settings = Settings(_env_file=None, database_url=NEON)  # pyright: ignore[reportCallIssue]
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.database_url.endswith("?sslmode=require&channel_binding=require")


def test_settings_repr_hides_database_url() -> None:
    settings = Settings(_env_file=None, database_url=NEON)  # pyright: ignore[reportCallIssue]
    assert "AbC123dEf" not in repr(settings)


def test_is_pooled_host() -> None:
    assert is_pooled_host(NEON_POOLED)
    assert not is_pooled_host(NEON)
    assert not is_pooled_host("postgresql+psycopg://coffer:coffer@localhost:5432/coffer")


def test_engine_options_direct() -> None:
    options = engine_options(normalize_database_url(NEON))
    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] > 0
    assert options["pool_size"] + options["max_overflow"] <= 20
    assert "connect_args" not in options


def test_engine_options_pooled_disables_prepared_statements() -> None:
    options = engine_options(normalize_database_url(NEON_POOLED))
    assert options["connect_args"] == {"prepare_threshold": None}


def test_engine_builds_without_connecting() -> None:
    url = normalize_database_url(NEON_POOLED)
    engine = create_engine(url, **engine_options(url))  # lazy: no network
    try:
        assert engine.dialect.driver == "psycopg"
        assert engine.url.query["sslmode"] == "require"
    finally:
        engine.dispose()
