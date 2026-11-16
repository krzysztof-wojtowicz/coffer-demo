# E5-05: Narzędzia budżetowe i obliczeniowe + akcje: oszczędności, wpływ zakupu, plan budżetu

**Fala:** E5/2 · **Zależności:** E5-02, E5-03 · **Role:** AI (eowyn) · **UC / wymagania:** UC-07, UC-11, F12–F15, F17, F31, F32, F37, N03, N08

## Cel
W katalogu są akcje `savings_analysis`, `purchase_impact`, `budget_plan` (E5-00 §K5), każda z deterministycznym fallbackiem; rejestr ma narzędzia `user_data`, `calc` i podstawowe `market` z E5-00 §K6 (wiersze E5-05). `simulate_purchase` jest czystą funkcją `analytics`.

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (§K1, §K2, §K5, §K6), `docs/use-cases/UC-07-assess-purchase-impact.md`
- `src/backend/coffer/agent/actions/{base,catalog,portfolio_review}.py`, `agent/tools/{registry,user_data,calc}.py`, `agent/runner.py` (tylko sygnatury)
- `src/backend/coffer/budget/service.py` (`month_summaries`, `month_insights`, `list_limits`), `src/backend/coffer/analytics/{compare,limits,allocation,portfolio}.py`
- `src/backend/coffer/market/service.py` (sygnatury `get_quotes`, `get_fx_rate`), `src/backend/coffer/transactions/service.py` (`list_views`)

## Pliki
- **eowyn:** `src/backend/coffer/agent/actions/{savings_analysis,purchase_impact,budget_plan,catalog}.py`, `agent/prompts/{savings_analysis_v1,purchase_impact_v1,budget_plan_v1}.md`, `agent/tools/{registry,user_data,calc,market_data}.py` (`market_data.py` nowy), `src/backend/coffer/analytics/{simulate,planning,spending}.py` (nowe), testy `src/backend/tests/agent/actions/{test_savings_analysis,test_purchase_impact,test_budget_plan}.py`, `tests/agent/tools/{test_user_data,test_calc,test_market_data}.py`, `tests/analytics/{test_simulate,test_planning,test_spending}.py`

## Kontrakt
**analytics (czyste):**
- `simulate.simulate_purchase(classes: Sequence[ClassValue], asset_class: str, amount: Decimal) -> PurchaseImpact` (`before`, `after`: `[ClassShare(asset_class, value, share_pct)]`, `total_before`, `total_after`, `new_class: bool`); pusty portfel → nowa klasa 100% (UC-07 3a); `amount > 0`.
- `planning.compound_growth(principal, monthly, annual_rate_pct, years) -> GrowthResult` (kapitalizacja miesięczna; `final_value, contributed, interest, yearly`), `planning.monthly_saving_for_goal(target, current, months, annual_rate_pct = 0) -> Decimal` (F17), `planning.propose_limits(averages: Mapping[int, tuple[str, Decimal]], growth_ids: set[int], cut_pct: Decimal) -> list[ProposedLimit]` (średnia, dla rosnących kategorii minus `cut_pct`, zaokrąglenie w górę do 10 zł).
- `spending.category_stats(views: Iterable[TxView]) -> list[CategoryStats]` (`count, total, average, largest` wydatków per kategoria; tylko kwoty, bez opisów).

**Narzędzia (opisy PL, wyjście tylko agregaty, kwoty jako stringi):**
- `user_data`: `get_months_overview(month, count 1–12)`, `get_spending_insights(month)` (= `budget.service.month_insights`), `get_transaction_stats(month, months 1–6)`, `get_category_limits(month)`.
- `calc`: `simulate_purchase(asset_class, amount)` (portfel użytkownika z `portfolio.service.summary`), `compound_interest(principal, monthly, annual_rate_pct 0–30, years 1–50)`, `savings_goal_plan(target, current, months, annual_rate_pct)`, `propose_budget(month, months_back, cut_pct 0–50)`.
- `market`: `get_quotes(symbols ≤ 10)`, `get_fx_rate(from_ccy, to_ccy)`; wynik z `fetched_at` i `source_url` (strona notowania Yahoo).

**Akcje:**
- `savings_analysis` (`month` domyślnie bieżący, `months_back` 1–6, domyślnie 3): `prepare` = `get_month_analysis`, `get_spending_insights`, `get_transaction_stats`; fakty: wydatki, nadwyżka, zmiana wydatków vs poprzedni miesiąc, liczba przekroczonych limitów; tabele `comparison` (F12), `top_growth` (F15), `limits` (F14); brak transakcji w miesiącu → `no_data` „Brak transakcji w wybranym miesiącu.”; `fallback`: rekomendacje dla przekroczonych limitów i top 3 wzrostów z kwotą „ograniczenie o 10% = X zł/mies., Y zł/rok”.
- `purchase_impact` (`asset_class` wymagane, `symbol?`, dokładnie jedno z `amount`/`quantity`, `price?`, `currency` PLN|EUR|USD|GBP|CHF): cena z `get_quotes` (`price` ręczna ma pierwszeństwo), przeliczenie na PLN `get_fx_rate`; `quantity` bez znanej ceny → `no_data` „Nie znamy ceny {symbol}. Podaj cenę ręcznie.” (UC-07 2a); tabela `allocation_change` (klasa, przed %, po %, zmiana p.p.); fakty: kwota zakupu PLN, nadwyżka ostatniego pełnego miesiąca (otwarta kwestia UC-07: tak, jako fakt), czy kwota ≤ nadwyżka; profil + `target_allocation` dla oceny; `fallback`: ocena regułowa (zbliża/oddala od celu, koncentracja klasy > cel + 10 p.p., brak profilu → UC-05). Zastrzeżenie inwestycyjne (F33).
- `budget_plan` (`months_back` 1–6 domyślnie 3, `savings_target?`, `target_months?`): tabela `proposed_limits` (kategoria, średnia, proponowany limit, obecny limit), fakty: średnie przychody/wydatki/nadwyżka, wymagana miesięczna kwota dla celu (F17), wynik `compound_interest` dla średniej nadwyżki na 5 lat przy 3%/rok (opisane jako przykład); `fallback`: propozycja z `propose_limits` (`cut_pct = 10`).
- Każda akcja: `tools` = podzbiór powyższych + `get_investment_profile`/`get_portfolio`/`target_allocation`, gdy potrzebne; `prompt` po polsku, wymaga odwołań do danych (F32) i zabrania liczb spoza wyników narzędzi.

## Testy (eowyn, `FakeLLM`, mocki rynku)
- Każda akcja: `ok` (poprawny draft), `unavailable` (fallback z niepustymi `findings`), `no_data`; tabele zgodne z `analytics` co do grosza.
- `simulate_purchase`: `hypothesis` – suma udziałów po = 100 ± 0.1, `total_after = total_before + amount`.
- Prywatność: `FakeLLM.calls` nie zawierają opisów transakcji ani nazw pozycji z fikstury.

## Kryteria akceptacji
- [ ] `make lint`; `COFFER_TEST_DB=coffer_test_eowyn make test-backend ARGS="tests/agent tests/analytics"`
- [ ] `GET /api/agent/actions` zwraca 4 akcje (z `portfolio_review`)
- [ ] **nie** uruchamiać `make openapi`

## Poza zakresem
Narzędzia historii cen, spółek, newsów (E5-07); zapisywanie proponowanych limitów (front E5-06, opcjonalnie).
