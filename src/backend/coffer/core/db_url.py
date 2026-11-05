"""Database URL handling shared by the app engine and Alembic.

Hosted Postgres providers (e.g. Neon) hand out URLs like
``postgresql://user:pass@host/db?sslmode=require&channel_binding=require``.
SQLAlchemy would pick the psycopg2 driver for such a URL, but the project uses psycopg 3,
so the scheme is rewritten to ``postgresql+psycopg://``. Only the scheme changes: the
credentials, host and query parameters (SSL settings) are kept verbatim.
"""

from typing import Any
from urllib.parse import urlsplit

DRIVER_SCHEME = "postgresql+psycopg"
_PLAIN_SCHEMES = ("postgres", "postgresql")

# Neon suspends idle computes and closes idle connections; the free tier has few connections.
POOL_SIZE = 5
MAX_OVERFLOW = 5
POOL_RECYCLE_S = 300


def normalize_database_url(url: str) -> str:
    """Return ``url`` with a ``postgres://``/``postgresql://`` scheme mapped to psycopg 3."""
    url = url.strip()
    scheme, sep, rest = url.partition("://")
    if sep and scheme.lower() in _PLAIN_SCHEMES:
        return f"{DRIVER_SCHEME}://{rest}"
    return url


def is_pooled_host(url: str) -> bool:
    """True for a PgBouncer endpoint (Neon marks it with ``-pooler`` in the host name)."""
    host = urlsplit(url).hostname or ""
    return "-pooler" in host


def engine_options(url: str) -> dict[str, Any]:
    """Keyword arguments for ``create_engine`` used by the application."""
    options: dict[str, Any] = {
        "pool_pre_ping": True,  # detect connections dropped while Neon was suspended
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_recycle": POOL_RECYCLE_S,
    }
    if is_pooled_host(url):
        # PgBouncer in transaction mode: server-side prepared statements may not survive
        # between transactions, so psycopg must not prepare them.
        options["connect_args"] = {"prepare_threshold": None}
    return options
