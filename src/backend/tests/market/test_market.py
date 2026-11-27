from decimal import Decimal

import pytest
import requests
from sqlalchemy import func, select, text

from coffer.market import service
from coffer.market.models import MarketQuote


def _rate(from_ccy, to_ccy):
    quote = service.get_fx_quote(from_ccy, to_ccy)
    return None if quote is None else quote[0]


pytestmark = pytest.mark.usefixtures("fake_yf")

PRICE = {"lastPrice": 10.0, "previousClose": 10.0, "currency": "USD"}


def test_quotes_parsed_as_decimal(fake_yf):
    quotes = service.get_quotes(["aapl", " PKO.WA ", "AAPL", ""])
    assert list(quotes) == ["AAPL", "PKO.WA"]
    aapl = quotes["AAPL"]
    assert aapl.price == Decimal("190.13")  # ROUND_HALF_UP
    assert aapl.change_pct == Decimal("2.77")
    assert aapl.currency == "USD"
    assert aapl.as_of.tzinfo is not None
    assert quotes["PKO.WA"].currency == "PLN"


def test_zero_previous_close_gives_no_change(fake_yf):
    assert service.get_quotes(["MSFT"])["MSFT"].change_pct is None


def test_unknown_symbol_skipped(fake_yf):
    assert set(service.get_quotes(["AAPL", "NOPE"])) == {"AAPL"}
    assert service.get_quotes(["NOPE"]) == {}


def test_network_error_raises(fake_yf):
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    with pytest.raises(service.MarketDataUnavailable):
        service.get_quotes(["AAPL"])


def test_cache(fake_yf):
    service.get_quotes(["AAPL", "NOPE"])
    service.get_quotes(["AAPL", "NOPE"])
    assert fake_yf.quote_calls == ["AAPL", "NOPE"]
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    assert "AAPL" in service.get_quotes(["AAPL"])  # served from cache


def test_network_error_stops_fetching(fake_yf):
    fake_yf.prices.update({"A": PRICE, "B": PRICE, "C": PRICE})
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    with pytest.raises(service.MarketDataUnavailable):
        service.get_quotes(["A", "B", "C"])
    assert fake_yf.quote_calls == ["A"]


def test_network_error_returns_cached(fake_yf):
    fake_yf.prices.update({"A": PRICE, "B": PRICE, "C": PRICE})
    service.get_quotes(["A"])
    fake_yf.fail_symbols["B"] = requests.exceptions.ConnectionError("down")
    assert set(service.get_quotes(["A", "B", "C"])) == {"A"}
    assert fake_yf.quote_calls == ["A", "B"]


def test_fx_rate_cached(fake_yf):
    fake_yf.prices["USDPLN=X"] = {"lastPrice": 3.987654, "currency": "PLN"}
    assert _rate("usd", "PLN") == Decimal("3.987654")
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    assert _rate("USD", "PLN") == Decimal("3.987654")
    assert fake_yf.quote_calls == ["USDPLN=X"]


def test_fx_rate_rounding(fake_yf):
    fake_yf.prices["EURPLN=X"] = {"lastPrice": 4.2512345}
    assert _rate("EUR", "PLN") == Decimal("4.251235")


def test_fx_same_currency_no_network(fake_yf):
    assert _rate("PLN", "pln") == Decimal("1")
    assert fake_yf.quote_calls == []


def test_fx_unknown_pair_and_network_error(fake_yf):
    assert _rate("XXX", "PLN") is None
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    assert _rate("USD", "PLN") is None


def test_offline_keyerror_is_network_error(fake_yf):
    # yfinance without network: connection fails internally, then surfaces as KeyError
    fake_yf.prices.clear()
    fake_yf.reachable = False
    with pytest.raises(service.MarketDataUnavailable):
        service.get_quotes(["A", "B", "C"])
    assert fake_yf.quote_calls == ["A"]
    assert service._quote_cache == {}
    fake_yf.reachable = True
    fake_yf.prices["A"] = PRICE
    assert "A" in service.get_quotes(["A"])  # nothing stale was cached


def test_offline_fx_not_cached(fake_yf):
    fake_yf.reachable = False
    assert _rate("USD", "PLN") is None
    assert service._fx_cache == {}
    fake_yf.reachable = True
    fake_yf.prices["USDPLN=X"] = {"lastPrice": 4.0}
    assert _rate("USD", "PLN") == Decimal("4.000000")


# Quote persistence


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


# Symbol validation
def test_malformed_symbols_never_reach_yfinance(fake_yf):
    evil = ["../../v1/finance/screener?x=1", "AAPL#frag", "A" * 500, "AA PL", "MSFT/../x"]
    quotes = service.get_quotes(["AAPL", *evil])
    assert fake_yf.quote_calls == ["AAPL"]
    assert list(quotes) == ["AAPL"]


def test_yahoo_style_symbols_still_work(fake_yf):
    fake_yf.prices["^GSPC"] = {"lastPrice": 1.0, "previousClose": 1.0, "currency": "USD"}
    service.get_quotes(["PKO.WA", "^GSPC", "BTC-USD", "USDPLN=X"])
    assert fake_yf.quote_calls == ["PKO.WA", "^GSPC", "BTC-USD", "USDPLN=X"]
