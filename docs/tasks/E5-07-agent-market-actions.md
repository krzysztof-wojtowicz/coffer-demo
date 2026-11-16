# E5-07: Narzędzia internetowe + akcje: nowe możliwości inwestycyjne, informacje o spółce

**Fala:** E5/3 · **Zależności:** E5-04, E5-05 · **Role:** AI (eowyn) · **UC / wymagania:** UC-06, UC-13, F31, F34, F35, F36, N03, N07, N08; E5-00 D7, D10

## Cel
Rejestr ma pełny zestaw narzędzi `market` (E5-00 §K6, wiersz E5-07), a katalog akcje `investment_ideas` i `company_research`. Każda informacja rynkowa w wyniku ma URL źródła i datę pobrania; `company_research` nie dostaje żadnych danych użytkownika. Katalog liczy 6 akcji.

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (§K1, §K2, §K5, §K6, D7, D10), `docs/use-cases/UC-06-find-opportunities.md`, `UC-13-company-info.md`
- `src/backend/coffer/agent/actions/{base,catalog,purchase_impact}.py`, `agent/tools/{registry,market_data}.py`, `agent/validator.py`
- `src/backend/coffer/market/service.py` (sygnatury z E5-04), `src/backend/coffer/analytics/market_stats.py`
- `git show HEAD:src/backend/coffer/agent/investment/advisor.py` (tylko `_score`, `fallback_picks`, `MAX_RISK`: wzór fallbacku)

## Pliki
- **eowyn:** `src/backend/coffer/agent/actions/{investment_ideas,company_research,catalog,portfolio_review,purchase_impact}.py` (w dwóch ostatnich tylko rozszerzenie `tools` o historię cen), `agent/prompts/{investment_ideas_v1,company_research_v1}.md`, `agent/tools/{registry,market_data}.py`, testy `src/backend/tests/agent/actions/{test_investment_ideas,test_company_research}.py`, `tests/agent/tools/test_market_data.py`

## Kontrakt
**Narzędzia `market`** (wszystkie `uses_internet=True`, wynik z `fetched_at` i `source_url`; błąd źródła → `{"error": "Dane rynkowe są chwilowo niedostępne"}`):
`get_price_history(symbol, period)` (punkty przerzedzone do ≤ 30 + `price_stats`), `get_company_profile(symbol)`, `get_company_news(symbol, limit ≤ 5)`, `get_market_news(limit ≤ 5)`, `search_symbol(query)`, `get_wikipedia_summary(query)`, `get_instrument_universe()`.

**investment_ideas** (`month?` domyślnie poprzedni pełny miesiąc, `amount?` domyślnie nadwyżka tego miesiąca, `asset_class?`):
- `prepare`: profil, `get_portfolio`, `get_months_overview(month, 1)`, `target_allocation`, `get_instrument_universe`; fakty: kwota do zainwestowania (źródło: podana / nadwyżka z miesiąca), maks. poziom ryzyka z profilu; kwota 0 i brak `amount` → `no_data` „Brak nadwyżki w wybranym miesiącu. Podaj kwotę ręcznie.” (zastępuje `no_surplus`, F31).
- Model może wołać: `get_quotes`, `get_price_history`, `get_company_news`, `get_market_news`, `search_symbol`, `get_instrument_universe`, `simulate_purchase`.
- `check`: 2–5 rekomendacji; każda z `symbol` widzianym w wynikach narzędzi, `risk_level ≤` maks. ryzyka profilu (krótki horyzont → maks. 2), `source_url` z wyników narzędzi; klasy z `asset_class` (jeśli podano).
- `fallback`: 3 propozycje z uniwersum wg punktacji zgodności z profilem i luką alokacji (port `fallback_picks`), `source_url` = strona notowania Yahoo, `sources` = `get_market_news` (jeśli dostępne). Zastrzeżenie inwestycyjne (F33).

**company_research** (`query`): `uses_user_data=False`; kontekst modelu zawiera wyłącznie `query` i wyniki narzędzi rynkowych.
- `prepare`: `search_symbol(query)` → brak trafień → `no_data` „Nie znaleziono spółki. Sprawdź nazwę lub ticker.” (UC-13 3a); pierwsze trafienie typu akcja/ETF → `get_company_profile`, `get_quotes`, `get_company_news(5)`, `get_price_history(1y)`; fakty: cena, zmiana 1 r., kapitalizacja, C/Z, stopa dywidendy, sektor; tabela `news` (data, tytuł, wydawca); `sources` = profil + newsy; inne trafienia jako fakt „Inne pasujące symbole”.
- Model może wołać: `get_company_news`, `get_price_history`, `get_wikipedia_summary`, `get_quotes`.
- `check`: co najmniej 1 `source_url` z wyników narzędzi (F35, UC-13 4b); `findings` bez `refers_to` w (`budget`, `profile`, `portfolio`).
- `fallback`: nagłówek z nazwą/sektorem, `findings` z opisu profilu (obcięty) i 3 najnowszych newsów, wszystkie źródła z datami. Zastrzeżenie: „Informacje mają charakter poglądowy i nie są rekomendacją; sprawdź źródła.”

## Testy (eowyn, mocki `market.service`, bez sieci)
- Obie akcje: `ok`, `unavailable` (fallback ze źródłami i `fetched_at`), `no_data`; `invalid`, gdy model poda URL/symbol spoza wyników narzędzi.
- `company_research`: `FakeLLM.calls` nie zawiera żadnej kwoty ani danych z fikstury użytkownika (wszystkie wiadomości porównane z danymi testowymi).
- `investment_ideas` bez `amount` i z nadwyżką 0 → `no_data`; z `amount` → działa mimo braku nadwyżki.

## Kryteria akceptacji
- [ ] `make lint`; `COFFER_TEST_DB=coffer_test_eowyn make test-backend ARGS="tests/agent"`
- [ ] `GET /api/agent/actions` zwraca 6 akcji, `GET /api/agent/tools` ≥ 20 narzędzi
- [ ] ręcznie (opcjonalnie, lokalny model): `company_research` dla „PKO BP” zwraca źródła z datami; wynik i czas w raporcie
- [ ] **nie** uruchamiać `make openapi`

## Poza zakresem
Natywne „web search” dostawców LLM, płatne API newsów, cache wyników akcji.
