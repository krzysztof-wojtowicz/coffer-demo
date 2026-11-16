# E5-10: Testy przekrojowe Etapu 5 (prywatność, izolacja, N08, ślad)

**Fala:** E5/4 · **Zależności:** E5-01..E5-09 · **Role:** testy (samwise) · **UC / wymagania:** N03, N07, N08, N09, F33, F35; E5-00 §K3, §K4

## Cel
Niezależne testy sprawdzają całość Etapu 5 przez API, na wszystkich 6 akcjach: do modelu trafiają tylko agregaty, cudze dane są niedostępne, każda akcja działa bez LLM, ślad jest kompletny, a usunięcie konta czyści nowe tabele. Znalezione błędy samwise opisuje w raporcie (właściciel, `plik:linia`), nie poprawia kodu produkcyjnego.

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (§K1–§K6)
- `src/backend/tests/conftest.py`, `src/backend/tests/agent/conftest.py`, `src/backend/coffer/agent/testing.py`
- `src/backend/coffer/agent/actions/catalog.py` (lista akcji i parametrów)

## Pliki
- **samwise:** `src/backend/tests/e5/` (nowy katalog: `__init__.py`, `conftest.py`, `test_privacy.py`, `test_isolation.py`, `test_fallback_all_actions.py`, `test_trace.py`, `test_limits_concurrency.py`, `test_account_delete.py`, `test_no_network.py`), `src/frontend/src/features/assistant/AssistantFlow.tester.test.tsx`

## Kontrakt (scenariusze)
- **Fikstura:** użytkownik z e-mailem `anna.kowalska@example.com`, transakcjami o unikalnych opisach (`SKLEP-SEKRET-123`), pozycją o nazwie „Konto u Jana” z notatką, profilem, limitem; drugi użytkownik z własnymi danymi; `market.service` w pełni zamockowany; blokada sieci (`socket.connect` → wyjątek) dla całego katalogu.
- **Prywatność (N03):** dla każdej akcji z `FakeLLM` żadna wiadomość (`FakeLLM.calls`, `agent_runs.messages`, `steps`) nie zawiera e-maila, opisów transakcji, nazwy/notatki pozycji, `user_id` ani id rekordów; `company_research` nie zawiera żadnej kwoty z danych użytkownika.
- **Izolacja:** `/runs`, `/suggestions` (z każdym filtrem), `/runs/{id}`, `/suggestions/{id}` drugiego użytkownika → 404 / brak w listach; `/api/budget/limits` izolowane; wszystkie nowe endpointy bez sesji → 401.
- **N08:** `llm=None`, `LLMUnavailable`, timeout, 2 niepoprawne odpowiedzi, limit wyczerpany → każda z 6 akcji zwraca 200, niepusty raport, `source=rules`, właściwy `ai_status`, zastrzeżenie (F33); sugestia zapisana w historii.
- **Ślad:** przebieg `ok` ma kroki z `started_ms` rosnącym, `duration_ms ≥ 0`, krok `llm` z dostawcą, modelem, tokenami, kosztem; suma `duration_ms` kroków ≤ czas przebiegu; `GET /runs?sort=cost_usd&order=desc` i filtry zwracają spójne `total`.
- **Źródła (N07, F35):** każdy element `sources` w wynikach `investment_ideas` i `company_research` ma `url` i `fetched_at`.
- **Limit współbieżny:** 5 uruchomień przy `agent_daily_limit=2` (falami po ≤ 2, bo guard dopuszcza maks. 2 równoległe przebiegi na użytkownika) → dokładnie 2 z `ai_status=ok`, reszta `limited`. Przy 5 w pełni równoległych nadmiar ponad 2 dostaje 429 (ochrona przed nadużyciem, audyt bezpieczeństwa), a `ok` ≤ 2.
- **Usunięcie konta (N09):** po `DELETE` konta brak wierszy w `agent_runs`, `suggestions`, `llm_usage_daily`, `budget_limits` dla użytkownika.
- **Front (vitest):** pełny przepływ: wybór akcji → parametry → SSE → raport → pozycja w historii po odświeżeniu (mock `fetch`).

## Kryteria akceptacji
- [ ] `COFFER_TEST_DB=coffer_test_samwise make test-backend ARGS="tests/e5"`; `make check-web`
- [ ] cały `make check` zielony; liczba testów i znalezione błędy w raporcie

## Poza zakresem
Testy e2e Playwright (karta E4-05), poprawki kodu produkcyjnego.
