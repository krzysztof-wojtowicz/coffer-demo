from sqlalchemy import create_engine, pool

import coffer.accounts.models
import coffer.agent.models
import coffer.cash.models
import coffer.imports.models
import coffer.portfolio.models
import coffer.profile.models
import coffer.transactions.models  # noqa: F401
from alembic import context
from coffer.core.config import get_settings
from coffer.core.db import Base
from coffer.core.db_url import normalize_database_url

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # Settings already normalize COFFER_DATABASE_URL; an explicit sqlalchemy.url may not be.
    return normalize_database_url(
        config.get_main_option("sqlalchemy.url") or get_settings().database_url
    )


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
