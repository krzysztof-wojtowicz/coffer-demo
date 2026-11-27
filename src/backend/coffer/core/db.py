from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from coffer.core.config import get_settings
from coffer.core.db_url import engine_options


class Base(DeclarativeBase):
    pass


_DATABASE_URL = get_settings().database_url
engine = create_engine(_DATABASE_URL, **engine_options())
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


def get_owned[T](db: Session, model: type[T], user_id: int, id: int) -> T | None:
    """The user's row or None; routers turn None into their own 404."""
    row = db.get(model, id)
    return row if row is not None and getattr(row, "user_id", None) == user_id else None
