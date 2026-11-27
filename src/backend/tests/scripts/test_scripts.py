import threading
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from coffer.accounts.policy import password_problems
from coffer.market import scheduler
from coffer.market.models import MarketQuote
from coffer.portfolio import service as portfolio_service
from coffer.portfolio.models import Holding
from coffer.scripts import refresh_prices, seed_demo

pytestmark = pytest.mark.usefixtures("fake_yf")


def _holding(db, user, symbol, currency="PLN", asset_class="stock"):
    db.add(
        Holding(
            user_id=user.id,
            name=symbol,
            asset_class=asset_class,
            symbol=symbol,
            quantity=Decimal("1"),
            purchase_price=Decimal("1.00"),
            currency=currency,
        )
    )
    db.commit()


def test_quoted_symbols_global(db, user, make_user):
    _holding(db, user, "AAPL")
    _holding(db, make_user(email="b@example.com"), "BTC", asset_class="crypto")
    _holding(db, user, "AAPL")
    assert portfolio_service.quoted_symbols(db) == ["AAPL", "BTC-USD"]


def test_script_refreshes_and_exits_zero_on_partial_failure(
    db, user, test_engine, fake_yf, monkeypatch, capsys
):
    _holding(db, user, "AAPL")
    _holding(db, user, "NOPE")
    fake_yf.prices["USDPLN=X"] = {"lastPrice": 4.0, "previousClose": 4.0, "currency": "PLN"}
    monkeypatch.setattr(refresh_prices, "SessionLocal", sessionmaker(bind=test_engine))
    refresh_prices.main()  # no exception -> exit code 0
    out = capsys.readouterr().out
    assert "updated: 2" in out and "NOPE" in out
    db.expire_all()
    symbols = set(db.scalars(select(MarketQuote.symbol)))
    assert symbols == {"AAPL", "USDPLN=X"}


def _noop_fetch(factory):
    return None


def test_scheduler_disabled_when_zero_hours():
    assert scheduler.start_price_scheduler(lambda: None, 0, _noop_fetch, lambda d, x: None) is None  # type: ignore[arg-type]


def test_scheduler_thread_runs_job_and_stops(test_engine):
    done = threading.Event()
    handle = scheduler.start_price_scheduler(
        sessionmaker(bind=test_engine),
        1,
        _noop_fetch,
        lambda db, data: done.set(),
        first_delay_s=0.01,
    )
    assert handle is not None and handle.thread.daemon
    assert done.wait(5)
    handle.stop()
    handle.thread.join(5)
    assert not handle.thread.is_alive()


def test_run_once_fetches_outside_transaction_and_skips_when_lock_held(test_engine):
    calls = []
    factory = sessionmaker(bind=test_engine)
    sessions_open = []

    def fetch(f):
        sessions_open.append(1)
        return "data"

    with factory() as holder:
        holder.execute(text("SELECT pg_advisory_lock(:id)"), {"id": scheduler.ADVISORY_LOCK_ID})
        assert scheduler.run_once(factory, fetch, lambda db, d: calls.append(d)) is False
        assert calls == [] and sessions_open == [1]
        holder.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": scheduler.ADVISORY_LOCK_ID})
        holder.commit()
    assert scheduler.run_once(factory, fetch, lambda db, d: calls.append(d)) is True
    assert calls == ["data"]


def test_fetch_stale_skips_fresh_and_refreshes_old(db, user, test_engine, fake_yf):
    factory = sessionmaker(bind=test_engine)
    _holding(db, user, "AAPL")
    fake_yf.prices["USDPLN=X"] = {"lastPrice": 4.0, "previousClose": 4.0, "currency": "PLN"}
    fetched = refresh_prices.fetch_all(factory)
    assert len(fetched.quotes) == 2
    with factory() as session:
        refresh_prices.store(session, fetched)
        session.commit()
    calls = len(fake_yf.quote_calls)
    again = refresh_prices.fetch_stale(factory, 1)
    assert again.quotes == [] and again.failed == []
    assert len(fake_yf.quote_calls) == calls
    # age the rows: they must be refreshed even though they are from today
    db.execute(text("UPDATE market_quotes SET fetched_at = fetched_at - interval '3 hours'"))
    db.commit()
    assert len(refresh_prices.fetch_stale(factory, 1).quotes) == 2
    assert refresh_prices.fetch_stale(factory, 6).quotes == []


# Seed
def test_demo_password_satisfies_policy() -> None:
    assert password_problems(seed_demo.DEMO_PASSWORD, seed_demo.DEMO_EMAIL) == []
