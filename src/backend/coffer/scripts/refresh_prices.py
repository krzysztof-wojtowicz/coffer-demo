"""Refresh held quotes and FX pairs into `market_quotes` (`make prices`).

Exit code is 0 also when some symbols failed: failures are only reported.
Network calls happen without an open transaction; only the final UPSERT is transactional.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from coffer.core.db import SessionLocal
from coffer.market import service as market
from coffer.market.scheduler import SessionFactory
from coffer.market.service import Quote
from coffer.portfolio import service as portfolio_service


@dataclass(frozen=True)
class Fetched:
    quotes: list[Quote]
    failed: list[str]


def fetch_all(session_factory: SessionFactory, max_age: timedelta | None = None) -> Fetched:
    """Fetch every held ticker and the PLN pair of every holding/quote currency.

    Database reads use short sessions that are closed before any network call.
    With `max_age`, symbols stored within that age are skipped (otherwise everything is
    refreshed).
    """
    with session_factory() as db:
        symbols = portfolio_service.quoted_symbols(db)
        holding_ccy = set(portfolio_service.holding_currencies(db))
        stored = market.stored_quotes(db, symbols)
        fresh = market.stored_quotes(db, symbols, max_age) if max_age else {}
    todo = [s for s in symbols if s not in fresh]
    first = market.fetch_quotes(todo)
    currencies = holding_ccy | {q.currency for q in stored.values()}
    currencies |= {q.currency for q in first.quotes}
    pairs = [f"{ccy}PLN=X" for ccy in sorted(currencies - {"PLN"}) if ccy.isalpha()]
    stored_pairs: dict[str, Quote] = {}
    if max_age and pairs:
        with session_factory() as db:
            stored_pairs = market.stored_quotes(db, pairs, max_age)
    second = market.fetch_quotes([p for p in pairs if p not in stored_pairs])
    return Fetched(first.quotes + second.quotes, first.failed + second.failed)


def fetch_stale(session_factory: SessionFactory, minutes: float) -> Fetched:
    """Scheduler fetch phase: only quotes older than `minutes` (or missing today)."""
    return fetch_all(session_factory, max_age=timedelta(minutes=minutes))


def store(db: Session, fetched: Fetched) -> None:
    market.store_quotes(db, fetched.quotes)


def main() -> None:
    fetched = fetch_all(SessionLocal)
    with SessionLocal() as db:
        store(db, fetched)
        db.commit()
    suffix = f" ({', '.join(fetched.failed)})" if fetched.failed else ""
    print(f"updated: {len(fetched.quotes)}, failed: {len(fetched.failed)}{suffix}")


if __name__ == "__main__":
    main()
