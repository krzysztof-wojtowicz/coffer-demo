"""Exploit: ticker symbols from the query string reach yfinance unvalidated.

yfinance puts the symbol into the request URL path (query*.finance.yahoo.com/.../{symbol}),
so `/`, `?`, `#` let a caller steer requests to other Yahoo endpoints; length is unbounded.
"""

URL = "/api/market/quotes"


def test_malformed_symbols_never_reach_yfinance(auth_client, fake_yf):
    evil = ["../../v1/finance/screener?x=1", "AAPL#frag", "A" * 500, "AA PL", "MSFT/../x"]
    r = auth_client.get(URL, params={"symbols": ",".join(["AAPL", *evil])})
    assert r.status_code == 200
    assert fake_yf.quote_calls == ["AAPL"]
    assert [q["symbol"] for q in r.json()["quotes"]] == ["AAPL"]


def test_yahoo_style_symbols_still_work(auth_client, fake_yf):
    fake_yf.prices["^GSPC"] = {"lastPrice": 1.0, "previousClose": 1.0, "currency": "USD"}
    r = auth_client.get(URL, params={"symbols": "PKO.WA,^GSPC,BTC-USD,USDPLN=X"})
    assert r.status_code == 200
    assert fake_yf.quote_calls == ["PKO.WA", "^GSPC", "BTC-USD", "USDPLN=X"]
