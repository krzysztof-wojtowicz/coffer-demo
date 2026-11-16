# E5-03: Silnik akcji agenta, nowe API, usunięcie nadwyżki i doradcy

**Fala:** E5/1 · **Zależności:** E5-01 · **Role:** AI (eowyn) · **UC / wymagania:** F23, F32, F33, F36, N03, N08; E5-00 D1–D6, D13

## Cel
Działa jeden mechanizm: katalog akcji + silnik `run_action` + endpoint `POST /api/agent/actions/{id}/run` (JSON i SSE), z pełnym śladem (§K4), atomowym limitem dziennym i fallbackiem. Pierwsza akcja referencyjna: `portfolio_review`. Stare funkcje „nadwyżka” i „rekomendacja” znikają z backendu.

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (całość, to Twój kontrakt)
- `src/backend/coffer/agent/{api,service,schemas,models,llm,sse,validator,testing}.py`, `agent/tools/{registry,user_data}.py`
- `src/backend/coffer/agent/investment/advisor.py` (tylko `run_tool_loop`, `_validate_answer`, `advise_for_user`: wzór pętli, potem plik usuwasz)
- `src/backend/coffer/portfolio/service.py` (`summary`), `src/backend/coffer/budget/service.py` (`net_worth`), `src/backend/coffer/analytics/portfolio.py`
- `src/backend/tests/agent/conftest.py`

## Pliki
- **eowyn – nowe:** `src/backend/coffer/agent/actions/{__init__,base,catalog,portfolio_review}.py`, `agent/runner.py`, `agent/trace.py`, `agent/pricing.py`, `agent/prompts/portfolio_review_v1.md`, `src/backend/coffer/analytics/allocation.py`
- **eowyn – zmiany:** `agent/{api,service,schemas,validator,testing,llm}.py`, `agent/tools/{registry,user_data}.py`, `agent/tools/calc.py` (nowy), `coffer/main.py` (usunięcie `investment_router`), `coffer/core/config.py` (`agent_timeout_s`), `.env.example`, `render.yaml` (zmiana nazwy zmiennej)
- **eowyn – usunięcie:** `agent/workflows/`, `agent/investment/`, `agent/drafts.py`, `agent/prompts/surplus_v1.md`, `surplus_v2.md`
- **eowyn – testy:** `src/backend/tests/agent/**` (usuń `test_surplus.py`, `test_surplus_api.py`, `test_investment_advice.py`, `test_vuln_advisor.py`, `test_history.py`, `test_runs.py`, `test_duration.py`; dopisz `test_runner.py`, `test_actions_api.py`, `test_runs_api.py`, `test_suggestions_api.py`, `test_usage_limit.py`, `test_pricing.py`, `actions/test_portfolio_review.py`, `tools/test_registry.py`), `src/backend/tests/integration/test_portfolio_advisor_e2e.py` (usuń), `src/backend/tests/analytics/test_allocation.py`

## Kontrakt
- Interfejs akcji, schemat raportu, API, ślad: E5-00 §K1–§K4 (bez odstępstw; doprecyzowania zapisz w raporcie).
- **LLM:** `LLMResponse.provider: str | None = None`; każdy klient ustawia swój dostawcę, `FallbackLLM` przekazuje dostawcę klienta, który odpowiedział. `FakeLLM` przyjmuje opcjonalne `provider`, `input_tokens`, `output_tokens` (do testów śladu i kosztu).
- **Rejestr:** `Tool` dostaje `group: Literal["user_data","market","calc"]`, `uses_internet: bool`; `ToolRegistry.call` mierzy czas, łapie wyjątki narzędzia i zwraca `{"error": "<komunikat PL>"}` ze statusem błędu (nie przerywa akcji); `ToolContext` dostaje `now`. `default_registry()` rejestruje wszystkie narzędzia; `registry.describe()` zasila `GET /tools`.
- **Narzędzia tej karty:** `get_portfolio` (klasy: wartość PLN, udział %; pozycje: `symbol`, `asset_class`, `value`, `share_pct`, `gain_pct`, `priced: bool`; `complete: bool`; bez `name`, `note`, `id`), `get_net_worth` (`cash_balance`, `portfolio_value`, `net_worth`, `portfolio_complete`), `target_allocation(risk, horizon)` (calc). Istniejące `get_month_analysis`, `get_investment_profile` bez zmian kontraktu.
- **analytics/allocation.py:** `target_allocation(risk: str, horizon: str) -> dict[str, Decimal]` (udziały % klas, suma 100; tabela reguł w kodzie, opisana w docstringu), `allocation_gap(current: Mapping[str, Decimal], target: Mapping[str, Decimal]) -> list[ClassGap]` (`asset_class, current_pct, target_pct, gap_pp`), `max_position_share(values: Sequence[Decimal]) -> Decimal | None`.
- **Silnik `run_action(db, user_id, action, params, llm, registry, on_event=noop) -> ActionRunOut`:** `prepare` (DB) → `no_data`? → `llm is None` → `unavailable` → `reserve_run` (odmowa → `limited`) → zwolnienie połączenia (`commit` + `close`, jak dziś) → pętla `call_tool`/`final` w budżecie `llm_deadline(agent_timeout_s)` z maks. `action.max_steps` wywołaniami → walidacja (`validator.validate_draft`: liczby, URL-e, symbole + `action.check`) z ponowieniem do `agent_max_attempts` niepoprawnych odpowiedzi → przy niepowodzeniu `fallback` → zapis `agent_runs` (steps, messages, tokeny, `cost_usd`, `provider`, `params`), `record_usage` (tokeny do `llm_usage_daily`) i `suggestions` (dla `ok` → `source=ai`, dla `unavailable|limited|timeout|invalid` → `source=rules`). Nieoczekiwany wyjątek: przebieg `error`, JSON → 500 „Nie udało się wykonać akcji”, SSE → zdarzenie `error`.
- **service.py:** `reserve_run(db, user_id, now, limit) -> bool` (atomowy `INSERT … ON CONFLICT (user_id, day) DO UPDATE SET runs = llm_usage_daily.runs + 1 RETURNING runs`), `record_usage(db, user_id, day, input_tokens, output_tokens)`, `list_runs(db, user_id, filters) -> (items, total)`, `list_suggestions(db, user_id, filters) -> (items, total)`; usuń `count_runs_today`.
- **pricing.py:** `estimate_cost(provider, model, input_tokens, output_tokens) -> Decimal | None`; Ollama → `0`; tabela USD/1M tokenów dla kilku rodzin modeli (dopasowanie po prefiksie), brak dopasowania lub tokenów → `None`; docstring: „szacunkowe, stan na <data>”.
- **portfolio_review:** `params` puste; `prepare`: `get_portfolio`, `get_investment_profile`, `get_net_worth`, `target_allocation` (profil domyślny `medium/medium`, gdy brak); fakty: wartość portfela, liczba pozycji, największa pozycja %, udział gotówki w majątku; tabela `allocation` (klasa, obecnie %, cel %, różnica p.p.); pusty portfel → `no_data` „Portfel jest pusty. Dodaj pozycje, aby uzyskać analizę.”; `fallback`: rebalans w stronę celu (klasy z `|gap| ≥ 10 p.p.`), ostrzeżenie o koncentracji (pozycja > 25%), brak profilu → zalecenie uzupełnienia (UC-05); model może wołać `get_quotes`/`get_price_history` dopiero po E5-05/E5-07 (teraz `tools = ("get_portfolio","get_investment_profile","get_net_worth","target_allocation")`).
- **Config:** `agent_timeout_s` (`COFFER_AGENT_TIMEOUT_S`, 60, `0 < x < 110`) zastępuje `advisor_timeout_s`; zaktualizuj `.env.example` i `render.yaml` (tylko ta zmienna).

## Testy (eowyn, tylko `FakeLLM` i mocki, bez sieci)
- Silnik na akcji testowej: ścieżki `ok`, `no_data`, `unavailable` (brak LLM i `LLMUnavailable`), `limited`, `timeout`, `invalid` (2 złe odpowiedzi → fallback), wywołanie narzędzia spoza `action.tools` (błąd w śladzie, model dostaje komunikat), błąd narzędzia nie przerywa akcji.
- Ślad: kroki mają `started_ms`/`duration_ms`, krok `llm` ma dostawcę, model, tokeny i koszt; suma tokenów w `llm_usage_daily`.
- `reserve_run`: dwa równoległe wywołania przy limicie 1 → dokładnie jedno `True`.
- API: 404 nieznanej akcji, 422 złych parametrów, SSE (`step`, `result`), filtry i sortowanie `/runs` i `/suggestions` (`total`, `offset`), cudzy przebieg/sugestia → 404, legacy sugestia (`surplus`) zwracana w nowym kształcie.
- `portfolio_review`: fallback deterministyczny, dane do modelu bez nazw/notatek pozycji i e-maila; walidator odrzuca liczbę spoza danych i URL spoza wyników narzędzi.

## Kryteria akceptacji
- [ ] `make lint` (import-linter: rdzeń nie importuje `agent`, `analytics` czyste)
- [ ] `COFFER_TEST_DB=coffer_test_eowyn make test-backend ARGS="tests/agent tests/analytics/test_allocation.py"` i cały `make test-backend` zielony
- [ ] `grep -rn "surplus\|advisor\|investment" src/backend/coffer/agent` → tylko etykiety legacy w mapowaniu historii (jeśli potrzebne)
- [ ] **nie** uruchamiać `make openapi` (E5-00 D12)

## Poza zakresem
Pozostałe akcje i narzędzia (E5-05, E5-07), front (E5-06), serwer MCP.
