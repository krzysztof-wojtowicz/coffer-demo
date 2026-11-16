from datetime import date, timedelta

import httpx
import pandas as pd
import pytest

from coffer.market import service


def test_price_history_ok_and_downsampled(monkeypatch):
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    frame = pd.DataFrame({"Close": [10 + i / 10 for i in range(400)]}, index=idx)
    monkeypatch.setattr(service, "_fetch_history", lambda s, p: frame)
    monkeypatch.setattr(service, "_fetch_currency", lambda s: "USD")
    h = service.get_price_history("aapl", "5y")
    assert h is not None and h.symbol == "AAPL" and h.currency == "USD"
    assert len(h.points) == 260 and h.points[0][0] == date(2024, 1, 1)
    assert h.points[-1][0] == date(2024, 1, 1) + timedelta(days=399)
    assert h.fetched_at and h.source_url.startswith("https://finance.yahoo.com/")


def test_price_history_bad_input_or_error(monkeypatch):
    assert service.get_price_history("???", "1y") is None
    assert service.get_price_history("AAPL", "2y") is None  # type: ignore[arg-type]

    def boom(s, p):
        raise OSError("down")

    monkeypatch.setattr(service, "_fetch_history", boom)
    assert service.get_price_history("AAPL", "1y") is None


def test_company_profile(monkeypatch):
    info = {
        "longName": "Apple Inc.",
        "sector": "Technology",
        "country": "United States",
        "longBusinessSummary": "x" * 2000,
        "marketCap": 3_000_000_000_000,
        "trailingPE": 31.5,
        "currency": "USD",
    }
    monkeypatch.setattr(service, "_fetch_info", lambda s: info)
    p = service.get_company_profile("AAPL")
    assert p is not None and p.name == "Apple Inc." and len(p.summary or "") == 1000
    assert p.pe_ratio is not None and p.dividend_yield is None
    assert p.source_url == "https://finance.yahoo.com/quote/AAPL/profile" and p.fetched_at


def test_company_profile_errors(monkeypatch):
    monkeypatch.setattr(service, "_fetch_info", lambda s: {})
    assert service.get_company_profile("AAPL") is None

    def boom(s):
        raise OSError

    monkeypatch.setattr(service, "_fetch_info", boom)
    service.clear_cache()
    assert service.get_company_profile("AAPL") is None


def test_company_news(fake_yf):
    tips = service.get_company_news("AAPL", 5)
    assert [t.title for t in tips] == ["Rynki rosną", "Złoto drożeje"] or len(tips) == 2
    assert all(t.fetched_at for t in tips)
    fake_yf.news_fail = OSError("down")
    assert service.get_company_news("AAPL") == []
    assert service.get_company_news("???") == []


def test_search_symbols_and_fallback(monkeypatch):
    monkeypatch.setattr(
        service,
        "_search_yahoo",
        lambda q, n: [
            {"symbol": "AAPL", "shortname": "Apple", "exchDisp": "NASDAQ", "quoteType": "EQUITY"}
        ],
    )
    [m] = service.search_symbols("apple")
    assert (m.symbol, m.name, m.exchange, m.type) == ("AAPL", "Apple", "NASDAQ", "EQUITY")

    def boom(q, n):
        raise OSError

    monkeypatch.setattr(service, "_search_yahoo", boom)
    assert [m.symbol for m in service.search_symbols("bitcoin")] == ["BTC-USD"]
    assert service.search_symbols("zzzzzz") == []
    assert service.search_symbols("  ") == []


class _Resp:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=None, response=None)  # type: ignore[arg-type]

    def json(self):
        return self._data


def test_wikipedia_summary(monkeypatch):
    seen = {}

    def fake_get(url, **kw):
        seen["headers"] = kw["headers"]
        seen["timeout"] = kw["timeout"]
        return _Resp(
            200,
            {
                "title": "Obligacja",
                "extract": "e" * 2000,
                "content_urls": {"desktop": {"page": "https://pl.wikipedia.org/wiki/Obligacja"}},
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    e = service.get_wikipedia_summary("Obligacja")
    assert e is not None and len(e.extract) == 1500 and e.url.endswith("/Obligacja")
    assert "Coffer" not in seen["headers"]["User-Agent"] and seen["timeout"] <= 10
    assert e.fetched_at


def test_wikipedia_errors(monkeypatch):
    def boom(url, **kw):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    assert service.get_wikipedia_summary("Obligacja") is None
    assert service.get_wikipedia_summary("x", lang="../evil") is None
    monkeypatch.setattr(httpx, "get", lambda url, **kw: _Resp(404, {}))
    assert service.get_wikipedia_summary("nic") is None


def test_with_timeout_gives_up_and_propagates_errors():
    import time

    with pytest.raises(TimeoutError):
        service._with_timeout(lambda: time.sleep(2), timeout=0.05)
    with pytest.raises(ValueError):
        service._with_timeout(lambda: (_ for _ in ()).throw(ValueError("x")), timeout=1)
    assert service._with_timeout(lambda: 5, timeout=1) == 5


def test_news_search_fx_quote_fetchers_use_timeout(monkeypatch):
    seen = []

    def fake_timeout(func, timeout=10.0):
        seen.append(timeout)
        raise TimeoutError

    monkeypatch.setattr(service, "_with_timeout", fake_timeout)
    with pytest.raises(TimeoutError):
        service._fetch_quote("AAPL")
    with pytest.raises(TimeoutError):
        service._fetch_fx_rate("USDPLN=X")
    with pytest.raises(TimeoutError):
        service._fetch_news("AAPL", 3)
    with pytest.raises(TimeoutError):
        service._search_yahoo("apple", 3)
    assert len(seen) == 4
    assert service.get_company_news("AAPL") == []
    assert service.search_symbols("bitcoin")[0].symbol == "BTC-USD"


def test_wikipedia_foreign_page_url_is_replaced(monkeypatch):
    data = {
        "title": "Obligacja",
        "extract": "e",
        "content_urls": {"desktop": {"page": "https://evil.example/x"}},
    }
    monkeypatch.setattr(httpx, "get", lambda url, **kw: _Resp(200, data))
    entry = service.get_wikipedia_summary("Obligacja")
    assert entry is not None and entry.url == "https://pl.wikipedia.org/wiki/Obligacja"


def test_news_title_is_trimmed():
    tip = service._parse_news_item({"title": "t" * 500, "publisher": "p" * 300})
    assert tip is not None and len(tip.title) == 200 and len(tip.source) == 100
