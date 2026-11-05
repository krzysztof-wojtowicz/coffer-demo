from collections.abc import Iterator
from typing import Any

import pytest
import yfinance

from coffer.market import service

PRICES: dict[str, dict[str, Any]] = {
    "AAPL": {"lastPrice": 190.125, "previousClose": 185.0, "currency": "USD"},
    "MSFT": {"lastPrice": 410.0, "previousClose": 0.0, "currency": "USD"},
    "PKO.WA": {"lastPrice": 55.555, "previousClose": 50.0, "currency": "pln"},
}

NEWS_NEW = {
    "id": "1",
    "content": {
        "title": "Rynki rosną",
        "summary": "<p>Indeksy w górę</p>",
        "pubDate": "2026-11-04T10:00:00Z",
        "provider": {"displayName": "Reuters"},
        "canonicalUrl": {"url": "https://example.com/a"},
    },
}
NEWS_OLD = {
    "title": "Złoto drożeje",
    "publisher": "Bloomberg",
    "link": "https://example.com/b",
    "providerPublishTime": 1762250400,
}


class FakeYF:
    def __init__(self) -> None:
        self.prices = dict(PRICES)
        self.news: list[dict[str, Any]] = [NEWS_NEW, NEWS_OLD]
        self.fail: Exception | None = None
        self.fail_symbols: dict[str, Exception] = {}
        self.news_fail: Exception | None = None
        self.quote_calls: list[str] = []
        self.reachable = True

    def ticker(self, symbol: str) -> Any:
        fake = self

        class _Ticker:
            @property
            def fast_info(self) -> Any:
                fake.quote_calls.append(symbol)
                if fake.fail is not None:
                    raise fake.fail
                if symbol in fake.fail_symbols:
                    raise fake.fail_symbols[symbol]
                if symbol not in fake.prices:
                    raise KeyError("currentTradingPeriod")
                return fake.prices[symbol]

            def get_news(self, count: int = 10) -> list[dict[str, Any]]:
                if fake.news_fail is not None:
                    raise fake.news_fail
                return fake.news[:count]

        return _Ticker()


@pytest.fixture(autouse=True)
def fake_yf(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeYF]:
    fake = FakeYF()
    monkeypatch.setattr(yfinance, "Ticker", fake.ticker)
    monkeypatch.setattr(service, "_source_reachable", lambda: fake.reachable)
    service.clear_cache()
    yield fake
    service.clear_cache()
