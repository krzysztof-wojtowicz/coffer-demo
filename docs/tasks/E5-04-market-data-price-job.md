# E5-04: Dane rynkowe z Internetu i dzienny job cen

**Fala:** E5/2 · **Zależności:** E5-01 · **Role:** backend (aragorn) · **UC / wymagania:** UC-04, UC-13, F22, F25, F34, F35, N07; E5-00 D7, D8; zastępuje backend karty E4-03

## Cel
`market.service` dostarcza (bez kluczy API) historię cen, profil spółki, newsy spółki, wyszukiwanie symboli i podsumowanie z Wikipedii, każde z `fetched_at` i `source_url`. Notowania są zapisywane w `market_quotes`, odświeżane komendą/jobem raz dziennie, a podsumowanie portfela podaje datę cen (`prices_as_of`).

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (D7, D8, D12, D13), `docs/tasks/E4-03-price-timestamps.md` (kontrakt `prices_as_of`)
- `src/backend/coffer/market/{service,models,api,schemas}.py`, `src/backend/coffer/portfolio/{service,schemas,api}.py`, `src/backend/coffer/analytics/portfolio.py`
- `src/backend/coffer/main.py`, `src/backend/coffer/core/config.py`, `Makefile`, `src/backend/tests/market/conftest.py`

## Pliki
- **aragorn:** `src/backend/coffer/market/{service,api,schemas,scheduler}.py` (`scheduler.py` nowy), `src/backend/coffer/portfolio/{service,schemas,api}.py`, `src/backend/coffer/analytics/market_stats.py` (nowy), `src/backend/coffer/scripts/refresh_prices.py` (nowy), `coffer/main.py` (lifespan), `coffer/core/config.py` (`price_refresh_hours`), `.env.example`, `render.yaml` (zmienna, wartość `0`), `Makefile` (`prices`), testy `src/backend/tests/market/**`, `tests/portfolio/test_prices_as_of.py`, `tests/analytics/test_market_stats.py`, `tests/scripts/test_refresh_prices.py`

## Kontrakt
**market/service.py** (funkcje nie rzucają przy błędzie źródła poza udokumentowanym `MarketDataUnavailable`; zwracają `None`/pustą listę; timeouty ≤ 10 s; cache w pamięci):
- `get_quotes(symbols, db: Session | None = None) -> dict[str, Quote]`: pamięć → `market_quotes` z dzisiejszą datą → źródło (+ `UPSERT` do bazy, gdy `db`). Bez `db` zachowanie jak dziś (serwer MCP).
- `refresh_quotes(db, symbols) -> RefreshReport(updated: int, failed: list[str])`.
- `get_price_history(symbol, period: Literal["1mo","3mo","6mo","1y","5y"]) -> PriceHistory | None` (`symbol, currency, points: list[(date, Decimal)]` maks. 260 punktów, `fetched_at`, `source_url`), cache 1 h.
- `get_company_profile(symbol) -> CompanyProfile | None` (`symbol, name, sector, industry, country, website, summary` ≤ 1000 zn., `market_cap, pe_ratio, dividend_yield, currency` jako `Decimal | None`, `fetched_at, source_url` = strona profilu Yahoo), cache 6 h.
- `get_company_news(symbol, limit ≤ 10) -> list[MarketTip]` (z `published_at`, `url`, `fetched_at`).
- `search_symbols(query, limit ≤ 10) -> list[SymbolMatch]` (`symbol, name, exchange, type`) przez `yf.Search`; fallback: dopasowanie w `get_instrument_universe()`.
- `get_wikipedia_summary(query, lang="pl") -> EncyclopediaEntry | None` (`title, extract` ≤ 1500 zn., `url, fetched_at`): `httpx`, endpointy REST Wikipedii, nagłówek `User-Agent: Coffer/1.0` (bez danych projektu/użytkownika).
- Docstring modułu: opis dwóch warstw (pamięć, baza) zamiast „no database”.

**analytics/market_stats.py:** `price_stats(points: Sequence[tuple[date, Decimal]]) -> PriceStats | None` (`first, last, min, max, return_pct, volatility_pct` roczna z odchylenia dziennych zwrotów × √252, `max_drawdown_pct`); < 2 punkty → `None`.

**Job cen (F25):**
- `portfolio.service.quoted_symbols(db) -> list[str]` (globalnie, wszystkie tickery z `holdings` po `quote_ticker`, bez danych użytkownika) i waluty pozycji → pary `XXXPLN=X`.
- `python -m coffer.scripts.refresh_prices` (`make prices`): odświeża wszystkie, wypisuje `updated/failed`, kod wyjścia 0 także przy częściowych błędach.
- `market/scheduler.py: start_price_scheduler(session_factory, hours) -> Thread | None`: wątek demon, pierwsze odświeżenie po 60 s, potem co `hours`; każde uruchomienie pod `pg_try_advisory_lock(<stała>)`; błędy tylko logowane. `main.py`: lifespan startuje go, gdy `price_refresh_hours > 0` (testy i domyślna konfiguracja: wyłączony).

**Portfel:** `portfolio.service.summary` przekazuje `db` do `get_quotes`; `GET /api/portfolio/summary` dostaje `prices_as_of: datetime | null` (najstarszy `as_of` użytych notowań i kursów) i `as_of: datetime | null` w pozycji z notowaniem (kontrakt E4-03). Zasady wyceny bez zmian.

## Testy (aragorn, mocki yfinance/httpx, bez sieci)
- Drugi odczyt notowania tego samego dnia po `clear_cache()` bierze bazę, nie źródło; `refresh_quotes` robi `UPSERT` (bez duplikatów PK).
- Każda funkcja internetowa przy wyjątku źródła zwraca `None`/`[]`; `fetched_at` i `source_url` obecne.
- `price_stats`: znane wartości na krótkiej serii; `hypothesis`: `min ≤ last ≤ max`, `max_drawdown_pct ≤ 0`.
- Skrypt na bazie testowej z mockiem; scheduler nie startuje przy `price_refresh_hours = 0`; `prices_as_of` = `null` bez notowań.

## Kryteria akceptacji
- [ ] `make lint`; `COFFER_TEST_DB=coffer_test_aragorn make test-backend ARGS="tests/market tests/portfolio tests/analytics tests/scripts"`
- [ ] `make mcp-market` działa bez bazy (test `tests/market/test_mcp_server.py` zielony)
- [ ] **nie** uruchamiać `make openapi` (robi orkiestrator na końcu fali)

## Poza zakresem
Narzędzia agenta (E5-05, E5-07), UI dat cen (E5-08), kursy NBP po dacie transakcji, workflow GitHub Actions dla joba.
