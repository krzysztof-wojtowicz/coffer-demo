from decimal import Decimal

import pytest
import requests

from coffer.market import service

PRICE = {"lastPrice": 10.0, "previousClose": 10.0, "currency": "USD"}


def test_quotes_parsed_as_decimal(fake_yf):
    quotes = service.get_quotes(["aapl", " PKO.WA ", "AAPL", ""])
    assert list(quotes) == ["AAPL", "PKO.WA"]
    aapl = quotes["AAPL"]
    assert aapl.price == Decimal("190.13")  # ROUND_HALF_UP
    assert aapl.change_pct == Decimal("2.77")
    assert aapl.currency == "USD" and aapl.name == "Apple Inc."
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


def test_tips_both_formats(fake_yf):
    tips = service.get_market_tips(5)
    assert [t.title for t in tips] == ["Rynki rosną", "Złoto drożeje"]
    assert tips[0].summary == "Indeksy w górę"
    assert tips[0].source == "Reuters" and tips[0].url == "https://example.com/a"
    assert tips[1].source == "Bloomberg" and tips[1].published_at is not None


def test_tips_limit(fake_yf):
    assert len(service.get_market_tips(1)) == 1


def test_tips_error_returns_empty(fake_yf):
    fake_yf.news_fail = requests.exceptions.Timeout("slow")
    assert service.get_market_tips() == []


def test_universe():
    universe = service.get_instrument_universe()
    classes = {i.asset_class for i in universe}
    assert classes == set(service.ASSET_CLASSES)
    assert all(1 <= i.risk_level <= 5 for i in universe)


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
    assert service.get_fx_rate("usd", "PLN") == Decimal("3.987654")
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    assert service.get_fx_rate("USD", "PLN") == Decimal("3.987654")
    assert fake_yf.quote_calls == ["USDPLN=X"]


def test_fx_rate_rounding(fake_yf):
    fake_yf.prices["EURPLN=X"] = {"lastPrice": 4.2512345}
    assert service.get_fx_rate("EUR", "PLN") == Decimal("4.251235")


def test_fx_same_currency_no_network(fake_yf):
    assert service.get_fx_rate("PLN", "pln") == Decimal("1")
    assert fake_yf.quote_calls == []


def test_fx_unknown_pair_and_network_error(fake_yf):
    assert service.get_fx_rate("XXX", "PLN") is None
    fake_yf.fail = requests.exceptions.ConnectionError("down")
    assert service.get_fx_rate("USD", "PLN") is None


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
    assert service.get_fx_rate("USD", "PLN") is None
    assert service._fx_cache == {}
    fake_yf.reachable = True
    fake_yf.prices["USDPLN=X"] = {"lastPrice": 4.0}
    assert service.get_fx_rate("USD", "PLN") == Decimal("4.000000")


def test_curl_error_is_network():
    from curl_cffi.requests.exceptions import RequestException

    assert not service._is_unknown_symbol_error(RequestException("dns"))
    assert service._is_unknown_symbol_error(KeyError("x"))
