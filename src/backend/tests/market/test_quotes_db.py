from decimal import Decimal

from sqlalchemy import func, select, text

from coffer.market import service
from coffer.market.models import MarketQuote


def _count(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(MarketQuote))


def test_quote_is_persisted_and_read_back_from_db(db, fake_yf):
    first = service.get_quotes(["AAPL"], db)["AAPL"]
    assert _count(db) == 1
    assert fake_yf.quote_calls == ["AAPL"]
    service.clear_cache()
    second = service.get_quotes(["AAPL"], db)["AAPL"]
    assert fake_yf.quote_calls == ["AAPL"]  # not fetched again: taken from the database
    assert second.price == first.price == Decimal("190.13")
    assert second.currency == "USD"


def test_without_db_nothing_is_persisted(db, fake_yf):
    service.get_quotes(["AAPL"])
    assert _count(db) == 0


def test_refresh_quotes_upserts_without_duplicates(db, fake_yf):
    report = service.refresh_quotes(db, ["AAPL", "NOPE", "pko.wa"])
    assert report.updated == 2 and report.failed == ["NOPE"]
    fake_yf.prices["AAPL"] = {"lastPrice": 200.0, "previousClose": 190.0, "currency": "USD"}
    report = service.refresh_quotes(db, ["AAPL"])
    assert report.updated == 1 and report.failed == []
    assert _count(db) == 2
    db.expire_all()
    row = db.get(MarketQuote, ("AAPL", service._today()))
    assert row is not None and row.price == Decimal("200.00000000")


def test_refresh_survives_source_errors(db, fake_yf):
    fake_yf.fail = OSError("down")
    report = service.refresh_quotes(db, ["AAPL"])
    assert report.updated == 0 and report.failed == ["AAPL"]


def test_fx_quote_persisted_with_timestamp(db, fake_yf):
    fake_yf.prices["USDPLN=X"] = {"lastPrice": 4.0123456, "previousClose": 4.0, "currency": "PLN"}
    found = service.get_fx_quote("USD", "PLN", db)
    assert found is not None and found[0] == Decimal("4.012346")
    service.clear_cache()
    calls = len(fake_yf.quote_calls)
    again = service.get_fx_quote("USD", "PLN", db)
    assert len(fake_yf.quote_calls) == calls
    assert again is not None and again[0] == Decimal("4.012346")


def test_get_quotes_leaves_commit_to_the_caller(db, fake_yf, test_engine):
    service.get_quotes(["AAPL"], db)
    db.rollback()
    assert _count(db) == 0
    service.clear_cache()
    service.get_quotes(["AAPL"], db)
    db.commit()
    assert _count(db) == 1


def test_stale_db_quote_is_not_served(db, fake_yf):
    service.get_quotes(["AAPL"], db)
    db.commit()
    db.execute(text("UPDATE market_quotes SET fetched_at = fetched_at - interval '7 hours'"))
    db.commit()
    service.clear_cache()
    fake_yf.prices["AAPL"] = {"lastPrice": 200.0, "previousClose": 190.0, "currency": "USD"}
    assert service.get_quotes(["AAPL"], db)["AAPL"].price == Decimal("200.00")
