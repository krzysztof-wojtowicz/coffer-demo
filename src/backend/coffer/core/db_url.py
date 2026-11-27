"""Database URL handling shared by the app engine and Alembic.

SQLAlchemy would pick the psycopg2 driver for a ``postgres://`` or ``postgresql://`` URL, but
the project uses psycopg 3, so the scheme is rewritten to ``postgresql+psycopg://``. Only the
scheme changes: credentials, host and query parameters are kept verbatim.
"""

from typing import Any

DRIVER_SCHEME = "postgresql+psycopg"
_PLAIN_SCHEMES = ("postgres", "postgresql")

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


def engine_options() -> dict[str, Any]:
    """Keyword arguments for ``create_engine`` used by the application."""
    return {
        "pool_pre_ping": True,  # detect connections dropped by the server
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_recycle": POOL_RECYCLE_S,
    }
