# E5-00: Decyzje architektoniczne Etapu 5 i wspólny kontrakt agenta

**Fala:** E5/— (dokument, gotowy) · **Zależności:** — · **Role:** architekt (gandalf) · **UC / wymagania:** UC-06, UC-07, UC-11, UC-12, UC-13; F12–F15, F25, F31–F37; N03, N07, N08

## Cel
Jedno źródło prawdy dla kart E5-01..E5-11: decyzje, wspólny kontrakt mechanizmu „akcji” agenta (interfejs w kodzie, schemat wyniku, API, ślad) i plan fal. Karty odwołują się do sekcji tego dokumentu (np. „E5-00 §K3”).

## Przeczytaj
Tylko ten plik i swoją kartę. Kod obecnego agenta (do usunięcia) czytaj wyłącznie, jeśli karta tego wymaga.

## Stan wyjściowy (zweryfikowany w kodzie)
- Dwie osobne funkcje AI: workflow nadwyżki (`agent/workflows/surplus.py`, `POST /api/agent/surplus[/stream]`, prompt `surplus_v2`) i doradca portfela (`agent/investment/*`, `POST /api/agent/investment/advice`, pętla tool calli przez structured output, `advisor_timeout_s`). Front: `AiPanel` z dwiema zakładkami (`AssistantPanel`, `AdvisorPanel`).
- `agent_runs` / `suggestions` (migracja 0003) zostają; limit dzienny liczony `COUNT(*)` (wyścig, odłożone z przeglądu E2–E3).
- `ToolRegistry` (`agent/tools/registry.py`) ma dwa narzędzia (`get_month_analysis`, `get_investment_profile`); dane rynkowe doradca bierze z `market/tools.py` (te same funkcje obsługuje serwer MCP).
- `market/service.py`: yfinance (notowania `fast_info`, kursy par `XXXPLN=X`, newsy `get_news`), cache w pamięci 5 min, bez bazy. yfinance 1.8 ma `yf.Search`.
- Brak limitów kategorii i porównań miesięcy (F12–F15), brak joba cen (F25), brak `prices_as_of` (karta E4-03 niezrealizowana).
- Import: deduplikacja po (data, kwota, opis z normalizacją spacji) względem transakcji w bazie działa (F05); kategoryzacja to słowa kluczowe (F07). Luki: `imports/service.py` importuje `coffer.transactions.models` (naruszenie granic), wczytuje wszystkie transakcje użytkownika, brak uczenia z poprawek użytkownika i brak zbioru N05 (200 transakcji). Zakres: karta E5-09.
- Migracje: head = `0006` (saldo początkowe). Plan numeracji z `docs/data-model.md` §4 jest nieaktualny (0006 zajęte inaczej); E5 numeruje od `0007`.

## Decyzje

**D1. Jeden mechanizm: akcja + jeden silnik.** Obie funkcje AI (nadwyżka, rekomendacja doradcy) znikają z kodu, API, frontu i testów. Zastępuje je katalog akcji (`agent/actions/`) obsługiwany jednym silnikiem `agent/runner.py`. Każda akcja implementuje ten sam interfejs (§K1). Uzasadnienie: dwa przepływy duplikowały limit, ślad, zapis sugestii i obsługę błędów; nowe funkcje (UC-07, UC-13) dochodzą jako kolejne akcje bez nowego endpointu.

**D2. Tool calling przez structured output, nie natywne API dostawców.** Silnik uogólnia protokół doradcy: model w każdym kroku zwraca JSON `{"action":"call_tool","tool":..,"args":{..}}` albo `{"action":"final","answer":{..}}`. Działa tak samo z Ollamą, OpenAI, Gemini, Anthropic i `FakeLLM`, bez zmian w `LLMClient.complete`. Model może wołać tylko narzędzia z `Action.tools`.

**D3. Liczby liczy kod, model pisze tylko narrację.** Wynik każdej akcji ma wspólny schemat raportu (§K2). Fakty (`facts`) i tabele (`tables`) zawsze pochodzą z części deterministycznej (`prepare`, funkcje `coffer.analytics`). Model dostarcza tylko `headline`, `findings`, `recommendations`, `risks`, `source_urls`. Walidacja: liczby w tekście muszą występować w danych z narzędzi (uogólniony `agent/validator.py`), URL-e i symbole muszą pochodzić z wyników narzędzi. Fallback (N08) zwraca ten sam schemat, więc front ma jeden renderer.

**D4. Jeden endpoint uruchomienia.** `POST /api/agent/actions/{action_id}/run`: z nagłówkiem `Accept: text/event-stream` zwraca SSE, w przeciwnym razie JSON (§K3). Brak LLM, limit, timeout i niepoprawna odpowiedź modelu dają **200 z wynikiem regułowym** i odpowiednim `ai_status` (nie 429): użytkownik zawsze dostaje wartość.

**D5. Ślad i limit.** `agent_runs` dostaje `provider`, `params`, `steps` (oś kroków z czasami), `llm_calls`, `cost_usd`; atomowy limit dzienny w nowej tabeli `llm_usage_daily` (`reserve_run` z `INSERT … ON CONFLICT … RETURNING`, decyzja (f) z `data-model.md` §2.8) zamyka wyścig `COUNT(*)`. Koszt szacuje statyczna tabela cen w `agent/pricing.py` (Ollama = 0, nieznany model = `null`). `LLMResponse` dostaje pole `provider` (który klient łańcucha `FallbackLLM` naprawdę odpowiedział).

**D6. Historia sugestii zapisuje każdy udany wynik** (`source: "ai"` albo `"rules"`), nie zapisuje `no_data` ani `error`. Stare wiersze (`surplus`, `advisor`) migracja konwertuje do schematu raportu (§K2) i zostają jako archiwalne; przebiegi zostają bez zmian (front pokazuje dla nich stary widok sekcji, gdy `steps` puste).

**D7. Dane z Internetu bez kluczy i płatnych usług:** yfinance (notowania akcji/ETF/krypto `BTC-USD`/walut `EURPLN=X`, historia cen, profil spółki `Ticker.info`, newsy `get_news`, wyszukiwanie `yf.Search`) + Wikipedia REST API (podsumowanie hasła, bez klucza, przez `httpx`, ogólny User-Agent bez danych projektu). Każdy wynik rynkowy ma `fetched_at` i `source_url` (N07). Akcja `company_research` nie dostaje danych użytkownika (UC-13 krok 2).

**D8. Job cen (F25) lokalnie i bez nowych usług.** Nowa globalna tabela `market_quotes (symbol, quote_date)` (bez danych osobowych; pary FX zapisywane jako symbole Yahoo `EURPLN=X`, osobne `fx_rates` z `data-model.md` §2.4 zostaje na później). Mechanizm: komenda `python -m coffer.scripts.refresh_prices` / `make prices` + opcjonalny wątek w procesie API (`COFFER_PRICE_REFRESH_HOURS`, domyślnie `0` = wyłączony, blokada `pg_try_advisory_lock`, żeby kilka workerów nie dublowało pracy). Wycena portfela czyta: pamięć (5 min) → baza (notowanie z dziś) → źródło (zapis do bazy). Render free usypia proces, więc wątek jest tylko wygodą; gwarancję daje leniwy odczyt z bazy + ręczny/cron `make prices`.

**D9. Budżet: limity i porównania w rdzeniu.** `budget_limits (user_id, category_id)` tylko dla kategorii `in_budget` (`data-model.md` §2.6), porównania F12 i wzrosty F15 jako czyste funkcje `analytics`, jeden endpoint `GET /api/budget/{month}/insights`. Kategorie nadal po `category_id` (kolumny `code` nie ma i E5 jej nie wprowadza).

**D10. F31 bez osobnej funkcji.** „Sugestia wykorzystania nadwyżki” to akcja `investment_ideas` z parametrem `month` (kwota domyślnie = nadwyżka miesiąca) oraz `budget_plan`. Wymagania się nie zmieniają; UC-12 przepisuje bilbo (E5-11).

**D11. Granice modułów bez zmian.** Akcje i narzędzia żyją w `coffer.agent` i używają rdzenia wyłącznie przez `service.py` oraz publiczne dataclassy/funkcje `coffer.analytics`. Nowe moduły `analytics/{compare,limits,allocation,simulate,planning,spending,market_stats}.py` są czyste (bez `sqlalchemy`, `fastapi`, `coffer.core.db`). Rdzeń nie importuje `coffer.agent`. Serwer MCP (`market/mcp_server.py`, `market/tools.py`) zostaje bez zmian funkcjonalnych.

**D12. Typy API (`openapi.json`, `schema.d.ts`).** Karty backendu **nie** uruchamiają `make openapi` (dwie karty w fali nadpisywałyby ten sam plik, a usunięcie starych endpointów w fali 1 łamałoby front). Regeneruje legolas na starcie E5-06 i E5-08 oraz orkiestrator na końcu każdej fali od 2. Między falą 1 a 2 orkiestrator nie commituje (stary front wołałby usunięte endpointy).

**D13. Konfiguracja.** `advisor_timeout_s` → `agent_timeout_s` (`COFFER_AGENT_TIMEOUT_S`, domyślnie 60, `0 < x < 110`, łączny budżet jednej akcji). Nowe: `price_refresh_hours` (`COFFER_PRICE_REFRESH_HOURS`, `0..24`, domyślnie 0). `agent_daily_limit` i `agent_max_attempts` bez zmian (limit wspólny dla wszystkich akcji).

## Kontrakt wspólny

### K1. Interfejs akcji (`agent/actions/base.py`)
```text
ParamSpec(name, label, kind, required, default=None, options=(), help=None)
  kind ∈ month | text | symbol | amount | quantity | int | select
Action (dataclass, frozen):
  id: str                 # snake_case, ≤ 30 znaków (mieści się w agent_runs.task / suggestions.type)
  name: str               # PL, do UI
  description: str        # PL, 1–2 zdania
  params_model: type[BaseModel]       # walidacja wejścia → 422
  params_ui: tuple[ParamSpec, ...]    # opis formularza dla frontu
  prompt_version: str     # plik agent/prompts/<prompt_version>.md (prompt systemowy)
  tools: tuple[str, ...]  # nazwy z rejestru, które MODEL może wywołać
  draft_model: type[ReportDraft]      # schemat odpowiedzi modelu (§K2)
  disclaimer: str
  uses_user_data: bool    # False → kontekst i narzędzia bez danych użytkownika
  uses_internet: bool
  max_steps: int = 5      # maks. wywołań modelu w jednej akcji
  prepare(ctx: ActionContext, params) -> Prepared        # deterministycznie, przez ctx.call(tool, args) (zapis w śladzie)
  fallback(prepared: Prepared, params) -> ReportDraft    # wynik bez AI, zawsze możliwy
  check(draft, prepared, seen: Seen) -> list[str]        # walidacja specyficzna, komunikaty PL (domyślnie [])
Prepared: facts, tables, sources, context: dict (JSON dla modelu, tylko agregaty),
          snapshot: dict (→ suggestions.data_snapshot), profile_snapshot: dict | None,
          no_data: str | None (komunikat PL; silnik kończy bez modelu ze statusem no_data)
ActionContext: db, user_id, now, call(tool_name, args) -> dict
Seen: urls: set[str], symbols: set[str], numbers (z wyników narzędzi i context)
```
Katalog: `agent/actions/catalog.py` → `ACTIONS: dict[str, Action]`, `get_action(id) -> Action | None`.

### K2. Schemat raportu (`agent/schemas.py`)
```text
ActionReport:
  headline: str
  facts: [{label, value: str, kind: money|percent|number|text|date}]
  tables: [{id, title, columns: [{key, label, kind}], rows: [{<key>: str}]}]
  findings: [{title, detail, refers_to: budget|profile|portfolio|market|calc, value: str|null}]
  recommendations: [{title, detail, symbol|null, asset_class|null, amount: str|null, risk_level: 1..5|null, source_url|null}]
  risks: [str]
  sources: [{title, url, publisher|null, published_at|null, fetched_at}]
  disclaimer: str
ReportDraft (odpowiedź modelu i wynik fallbacku):
  headline (1–200 zn.), findings (1–6), recommendations (0–5), risks (0–5), source_urls: [str] (0–10)
```
Kwoty i procenty to stringi (`"1234.50"`, `"12.5"`). `sources` = źródła z `prepare` ∪ (`source_urls` ∩ URL-e widziane w wynikach narzędzi), każde z `fetched_at`.

### K3. API (`agent/api.py`, prefiks `/api/agent`, wszystko wymaga `CurrentUser`)
| Metoda, ścieżka | Wejście | Wyjście | Błędy |
|---|---|---|---|
| `GET /actions` | — | `[{id, name, description, params: [ParamSpec], tools: [str], uses_user_data, uses_internet}]` | — |
| `GET /tools` | — | `[{name, description, group: user_data\|market\|calc, uses_internet, parameters: JSONSchema}]` | — |
| `POST /actions/{action_id}/run` | `{params: {...}}`; `Accept: text/event-stream` → SSE | `ActionRunOut` | 404 „Nie znaleziono akcji”; 422 (parametry) |
| `GET /suggestions` | `action?`, `source? (ai\|rules)`, `date_from?`, `date_to?`, `q?` (≤100, w nagłówku), `order=desc\|asc`, `limit=5 (1–50)`, `offset=0` | `{items: [SuggestionOut], total}` | — |
| `GET /suggestions/{id}` | — | `SuggestionOut` | 404 „Nie znaleziono sugestii” |
| `GET /runs` | `action?`, `status?`, `provider?`, `date_from?`, `date_to?`, `sort=created_at\|duration_ms\|cost_usd\|tokens`, `order=desc\|asc`, `limit=20 (1–100)`, `offset=0` | `{items: [AgentRunListItem], total}` | — |
| `GET /runs/{id}` | — | `AgentRunOut` | 404 „Nie znaleziono przebiegu agenta” |
| `GET /status` | — | bez zmian | — |

```text
ActionRunOut: action, run_id|null, suggestion_id|null,
  ai_status: ok|unavailable|limited|timeout|invalid|no_data, source: ai|rules|none,
  report: ActionReport, model|null, provider|null, duration_ms
SuggestionOut: id, action, source, ai_status, headline, report, params, model|null, provider|null,
  run_id|null, created_at, profile_used: bool
AgentRunListItem: id, action, status, provider|null, model|null, llm_calls, tool_calls_count,
  input_tokens|null, output_tokens|null, cost_usd: str|null, duration_ms|null, created_at, suggestion_id|null
AgentRunOut = AgentRunListItem + params, prompt_version, steps, messages, raw_outputs,
  validation_errors, error|null, tool_calls (legacy)
```
Zdarzenia SSE: `status {message}`, `step {index, kind, name, status, duration_ms}`, `result ActionRunOut`, `error {detail}`; keepalive `: ping` jak dziś (`agent/sse.py`). Cudzy zasób → 404; filtry zawsze z `user_id`.

### K4. Ślad (`agent_runs.steps`, `agent/trace.py`)
```text
Step: {index, kind: tool|llm|validation|fallback|limit|error, name, started_ms (od startu przebiegu),
       duration_ms, status: ok|error,
       tool:       arguments, output (obcięte do 20 000 zn.), error|null, origin: prepare|model
       llm:        provider, model, attempt, input_tokens|null, output_tokens|null, cost_usd|null, output (surowa odpowiedź)
       validation: errors: [str]
       fallback:   reason (ai_status)}
```
`messages` (prompt systemowy + cała rozmowa) i `raw_outputs` jak dziś. Statusy przebiegu: `ok, invalid, unavailable, limited, timeout, no_data, error` (+ legacy `no_surplus`).

### K5. Katalog akcji (min. 6)
| id | Nazwa (UI) | Parametry | Wymaganie | Karta |
|---|---|---|---|---|
| `portfolio_review` | Analiza portfela | — | F23, F32, F36 | E5-03 |
| `savings_analysis` | Gdzie zaoszczędzić | `month`, `months_back=3` (1–6) | F12, F14, F15, F32 | E5-05 |
| `purchase_impact` | Wpływ zakupu na portfel | `asset_class`, `symbol?`, `amount?` \| `quantity?` + `price?`, `currency=PLN` | UC-07, F37 | E5-05 |
| `budget_plan` | Plan budżetu | `months_back=3`, `savings_target?`, `target_months?` (1–120) | F13, F17, F31 | E5-05 |
| `investment_ideas` | Nowe możliwości inwestycyjne | `month?`, `amount?`, `asset_class?` | UC-06, F31, F36, N07 | E5-07 |
| `company_research` | Informacje o spółce | `query` (1–60 zn., `[\w .&-]`) | UC-13, F34, F35, N07 | E5-07 |

### K6. Katalog narzędzi (jeden rejestr `agent/tools/registry.py`)
| Grupa | Narzędzia | Karta |
|---|---|---|
| user_data | `get_investment_profile`, `get_month_analysis` (istnieją), `get_portfolio`, `get_net_worth` | E5-03 |
| user_data | `get_months_overview`, `get_spending_insights`, `get_transaction_stats`, `get_category_limits` | E5-05 |
| calc | `target_allocation` | E5-03 |
| calc | `simulate_purchase`, `compound_interest`, `savings_goal_plan`, `propose_budget` | E5-05 |
| market | `get_quotes`, `get_fx_rate` | E5-05 |
| market | `get_price_history`, `get_company_profile`, `get_company_news`, `get_market_news`, `search_symbol`, `get_wikipedia_summary`, `get_instrument_universe` | E5-07 |

Prywatność (N03): narzędzia `user_data` zwracają tylko agregaty: bez e-maila, opisów transakcji, nazw i notatek pozycji, identyfikatorów (`id`, `user_id`). Pozycje portfela opisuje symbol + klasa + wartość + udział.

## Plan fal
| Fala | gimli (migracje) | aragorn (backend) | eowyn (AI) | legolas (frontend) | samwise / bilbo |
|---|---|---|---|---|---|
| 0 | E5-01 | | | | |
| 1 | | E5-02 | E5-03 | | |
| 2 | | E5-04 | E5-05 | E5-06 | |
| 3 | | E5-09 | E5-07 | E5-08 | |
| 4 | | | | | E5-10 (samwise) |
| 5 | | | | | E5-11 (bilbo) |

Pliki współdzielone w falach: `main.py` (fala 1 eowyn, fala 2 aragorn), `core/config.py` (fala 1 eowyn, fala 2 aragorn), `.env.example`/`render.yaml` (fala 1 eowyn, fala 2 aragorn), `Makefile` (fala 2 aragorn), `i18n/pl.ts` i `App.tsx` (tylko legolas). Edycja minimalna narzędziem Edit.

## Ryzyka
- yfinance bywa niestabilne i ograniczane (szczególnie `Ticker.info`): krótkie timeouty, cache, narzędzie zwraca `{"error": ...}` zamiast wyjątku; testy tylko z mockami.
- Małe modele lokalne gubią protokół JSON w wielu krokach: limit kroków, fallback regułowy, `invalid` w śladzie.
- Zagnieżdżony schemat odpowiedzi (koperta + `ReportDraft`) przy konwerterach Gemini/Anthropic: test schematów w E5-03.
- Tabela cen modeli się starzeje: koszt jest „szacunkowy”, UI to mówi.
- E5-03 jest największą kartą; jeśli przekroczy budżet, orkiestrator wydziela `portfolio_review` do E5-05.

## Kryteria akceptacji
- [x] Karty E5-01..E5-11 mają rozłączne pliki w obrębie fali i maks. 3 agentów na falę.
- [x] Wiersze E5 w `docs/tasks/README.md`.
