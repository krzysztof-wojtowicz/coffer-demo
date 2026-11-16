# E5-02: Porównania miesięcy i limity kategorii (backend)

**Fala:** E5/1 · **Zależności:** E5-01 · **Role:** backend (aragorn) · **UC / wymagania:** UC-11, F12, F13, F14, F15, N04

## Cel
Użytkownik może ustawić miesięczny limit dla kategorii budżetowej, a API zwraca dla miesiąca: zmianę wydatków per kategoria względem poprzedniego miesiąca (F12), 3 kategorie o największym wzroście względem średniej z 3 poprzednich miesięcy (F15) i wykorzystanie limitów z oznaczeniem przekroczeń (F14). Te same funkcje serwisu wykorzystają narzędzia agenta (E5-05).

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (D9, D11)
- `src/backend/coffer/analytics/month.py`, `src/backend/coffer/budget/{api,service,schemas,models}.py`, `src/backend/coffer/transactions/service.py` (`list_categories`, `list_views`)
- `src/backend/coffer/scripts/seed_demo.py`, `src/backend/tests/conftest.py`, `src/backend/tests/budget/test_budget_api.py`

## Pliki
- **aragorn:** `src/backend/coffer/analytics/{month,compare,limits}.py` (`compare.py`, `limits.py` nowe), `src/backend/coffer/budget/{api,service,schemas}.py`, `src/backend/coffer/scripts/seed_demo.py` (2 limity demo), testy `src/backend/tests/budget/test_insights.py`, `test_limits_api.py`, `src/backend/tests/analytics/{test_compare,test_limits}.py`

## Kontrakt
**analytics (czyste funkcje, `Decimal`, `quantize`):**
- `CategoryTotal` dostaje pole `in_budget: bool = True` (ostatnie, z domyślną wartością; `month_summary` je wypełnia).
- `compare.compare_months(current: MonthSummary, previous: MonthSummary) -> list[CategoryChange]`: suma kategorii z wydatkami w którymkolwiek miesiącu; `change = current - previous`, `change_pct = change / previous × 100` (1 miejsce po przecinku, `None` gdy `previous == 0`); sortowanie po `|change|` malejąco, potem nazwie.
- `compare.top_growth(current: MonthSummary, history: Sequence[MonthSummary], n: int = 3) -> list[CategoryGrowth]`: tylko `in_budget`; `average_3m` = średnia z miesięcy `history` (miesiąc bez wydatków w kategorii liczy się jako 0); tylko `increase > 0`; maks. `n`, sortowanie po `increase` malejąco.
- `limits.limit_status(by_category: Sequence[CategoryTotal], limits: Mapping[int, tuple[str, Decimal]]) -> list[LimitStatus]` (`category_id, category_name, limit, spent, remaining, used_pct, exceeded = spent > limit`); kategoria z limitem bez wydatków ma `spent = 0.00`.

**budget/service.py:**
- `list_limits(db, user_id) -> list[LimitView]`, `set_limit(db, user_id, category_id, amount) -> LimitView` (rzuca `UnknownCategoryError`, `NotBudgetCategoryError`), `delete_limit(db, user_id, category_id) -> bool`.
- `month_summaries(db, user_id, month, count) -> list[MonthSummary]` (miesiąc `month` i `count-1` poprzednich, od najnowszego; jedno zapytanie `list_views` na cały zakres).
- `month_insights(db, user_id, month) -> MonthInsights` (dataclass: `month, previous_month, comparison, top_growth, limits`).

**API (`/api/budget`, `CurrentUser`; trasy limitów deklarowane PRZED `/{month}`):**
- `GET /limits` → `[{category_id, category_name, amount}]` (po nazwie).
- `PUT /limits/{category_id}` `{amount: "500.00"}` (`Decimal > 0`, maks. 2 miejsca, ≤ 999 999 999 999.99) → `{category_id, category_name, amount}`; 404 „Nie znaleziono kategorii”; 422 „Limit można ustawić tylko dla kategorii budżetowej”.
- `DELETE /limits/{category_id}` → 204; 404 „Nie ustawiono limitu dla tej kategorii”.
- `GET /{month}/insights` → `{month, previous_month, comparison: [{category_id, category_name, current, previous, change, change_pct|null}], top_growth: [{category_id, category_name, current, average_3m, increase, increase_pct|null}], limits: [{category_id, category_name, limit, spent, remaining, used_pct, exceeded}]}`; kwoty i procenty jako stringi.
- Limity innego użytkownika są niewidoczne (filtr `user_id`); `GET /api/budget/{month}` bez zmian kształtu.

## Testy (aragorn)
- `hypothesis`: suma `current` w `comparison` = `expenses` miesiąca co do grosza (N04); `top_growth` ≤ 3 i tylko kategorie budżetowe.
- API: PUT/GET/DELETE, 404/422 z komunikatami, izolacja użytkowników, przekroczenie oznaczone `exceeded = true`, miesiąc bez poprzednich danych (średnia z zer, `change_pct = null`).

## Kryteria akceptacji
- [ ] `make lint` (import-linter: `analytics` czyste)
- [ ] `COFFER_TEST_DB=coffer_test_aragorn make test-backend ARGS="tests/budget tests/analytics"`
- [ ] **nie** uruchamiać `make openapi` (E5-00 D12)

## Poza zakresem
UI (E5-08), cele oszczędnościowe F16/F17 w bazie, limity per miesiąc.
