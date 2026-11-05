from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from coffer.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


def get_session_factory() -> sessionmaker[Session]:
    """For work that outlives the request scope (e.g. an SSE stream run in a worker thread).

    The caller opens and closes its own sessions. Tests override this dependency.
    """
    return SessionLocal


SessionFactory = Annotated[sessionmaker[Session], Depends(get_session_factory)]
