"""Periodic quote refresh in a daemon thread (F25). Disabled unless `hours > 0`.

Each run has two phases: `fetch` talks to the network without any open database
transaction, then `store` writes in a short transaction guarded by an advisory lock.
Both are injected, so this module does not depend on the portfolio.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

ADVISORY_LOCK_ID = 727_250_001
FIRST_RUN_DELAY_S = 60.0

SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class PriceScheduler:
    thread: threading.Thread
    _stop: threading.Event

    def stop(self) -> None:
        self._stop.set()


def run_once[T](
    session_factory: SessionFactory,
    fetch: Callable[[SessionFactory], T],
    store: Callable[[Session, T], object],
) -> bool:
    """fetch (no transaction), then store under a transaction-level advisory lock + commit.

    Another instance holding the lock makes the write a no-op. Never raises; True when stored.
    """
    try:
        data = fetch(session_factory)
        with session_factory() as db:
            params = {"id": ADVISORY_LOCK_ID}
            if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:id)"), params):
                log.info("price refresh skipped: another instance holds the lock")
                return False
            store(db, data)  # must not commit: the lock lives as long as this transaction
            db.commit()
            return True
    except Exception:
        log.warning("price refresh failed", exc_info=True)
        return False


def start_price_scheduler[T](
    session_factory: SessionFactory,
    hours: float,
    fetch: Callable[[SessionFactory], T],
    store: Callable[[Session, T], object],
    first_delay_s: float = FIRST_RUN_DELAY_S,
) -> PriceScheduler | None:
    if hours <= 0:
        return None
    stop = threading.Event()

    def loop() -> None:
        delay = first_delay_s
        while not stop.wait(delay):
            run_once(session_factory, fetch, store)
            delay = hours * 3600

    thread = threading.Thread(target=loop, name="price-scheduler", daemon=True)
    thread.start()
    return PriceScheduler(thread, stop)
