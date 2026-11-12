# Zadania: tablica statusu

Edytuje wyłącznie orkiestrator (proces: `.claude/skills/run-task/SKILL.md`). Statusy: `todo` → `ready` → `in-progress` → `done`.
Karty jednej fali mają rozłączne pliki i mogą iść równolegle. Nowa karta: [`_template.md`](_template.md).

## Etap 1: szkielet end-to-end (demo)

| Karta | Fala | Role | Zależności | Status | Notatka |
|---|---|---|---|---|---|
| [E1-01 Szkielet monorepo](E1-01-scaffold.md) | 0 | implementer | — | done | TS przypięty do ~5.9 (openapi-typescript); ruff B008 wyłączone dla `api.py` |
| [E1-02 Konta](E1-02-accounts.md) | 1 | implementer + tester | E1-01 | done | 60 testów; stały czas odpowiedzi dla nieznanego e-maila (dummy hash) |
| [E1-03 Transakcje](E1-03-transactions.md) | 1 | implementer + tester | E1-01 | done | 43 testy; tester wykrył błąd seeda kategorii w migracji E1-01 (poprawiony) |
| [E1-04 Analytics + budżet](E1-04-budget-analytics.md) | 1 | implementer + tester | E1-01 | done | 28 testów (w tym hypothesis); dodatnia kwota zawsze = przychód |
| [E1-05 Agent: sugestia nadwyżki](E1-05-agent-surplus.md) | 1 | implementer + tester | E1-01 | done | 36 testów (FakeLLM); ręcznie z qwen3:8b: `ok`, ~14 s |
| [E1-06 Frontend](E1-06-frontend.md) | 2 | implementer | E1-02..05 | done | rejestracja od razu loguje; kwota z przecinkiem zamieniana na kropkę |
| [E1-07 Dane demo + README](E1-07-demo-seed.md) | 2 | implementer (haiku) | E1-02, E1-03 | done | 94 transakcje, 4 miesiące; wynagrodzenie 1. dnia |
| Przegląd fal 1–2 | 3 | reviewer | E1-06, E1-07 | done | Poprawione: 500 dla miesięcy spoza 1900–2099 i kwot typu 1e30, połączenie DB trzymane w trakcie LLM, deficyt w demo na początku miesiąca (+9 testów regresji) |

### Uwagi z przeglądu na Etap 2
- Czyszczenie wygasłych sesji (`auth_sessions`), np. job w workerze.
- `OriginMiddleware` przepuszcza żądania bez nagłówka `Origin` (świadomie, ochrona przez SameSite=Lax); do decyzji przy wdrożeniu.

## Etap 2 (część 1): import CSV, Tailwind, panel asystenta

| Karta | Fala | Role | Zależności | Status | Notatka |
|---|---|---|---|---|---|
| [E2-01 Import CSV (backend)](E2-01-csv-import.md) | 1 | implementer + tester | E1 | done | 52 testy; `transactions.service.bulk_create`; indeksy wierszy od 0 |
| [E2-02 Tailwind + MonthPicker](E2-02-frontend-tailwind.md) | 1 | implementer + tester | E1-06 | done | 15 testów UI; nazwy miesięcy jako stała lista |
| [E2-04 Status modelu AI](E2-04-agent-status.md) | 1 | implementer + tester | E1-05 | done | 16 testów; `duration_ms` w `suggestion` |
| [E2-03 Strona importu](E2-03-import-ui.md) | 2 | implementer | E2-01, E2-02 | done | upload przez `fetch` + `FormData`; ręcznie: 17 nowych / 1 błąd, ponownie 17 duplikatów |
| [E2-05 Panel asystenta](E2-05-assistant-panel.md) | 2 | implementer + tester | E2-02, E2-04 | done | 25 testów; `fetch` zamiast openapi-fetch (AbortController), typy ze `schema.d.ts` |

## Etap 3: agent M

Fundament (E3-00, orkiestrator): modele `InvestmentProfile`, `AgentRun`, `Suggestion`, migracja `0003`, `get_session_factory`, ustawienia `agent_daily_limit`, `agent_max_attempts`. Poprawka wylogowania (orkiestrator): `lib/queryClient.ts`, globalna obsługa 401.

| Karta | Fala | Role | Zależności | Status | Notatka |
|---|---|---|---|---|---|
| [E3-01 Profil (backend)](E3-01-profile.md) | 1 | implementer + tester | E3-00 | done | 19 testów |
| [E3-02 Narzędzia, walidator, anonimizacja](E3-02-agent-tools.md) | 1 | implementer + tester | E3-00 | done | 61 testów; horyzont: do 2 lat / 2–5 / >5 (decyzja orkiestratora, UC-05 zostawiał otwarte) |
| [E3-03 Workflow nadwyżki v2 + SSE](E3-03-surplus-workflow.md) | 1 | implementer + tester | kontrakty E3-01, E3-02 | done | 60 testów; ręcznie qwen3:8b: `ok` w 1. próbie, 22 s, bez PII w śladzie |
| [E3-04 Ciemny motyw](E3-04-dark-theme.md) | 1 | implementer | E2 | done | tokeny semantyczne w `@theme` |
| [E3-05 Frontend: profil, SSE, historia, ślad](E3-05-frontend-agent.md) | 2 | implementer + tester | E3-01, E3-03, E3-04 | done | 23 nowe testy; orkiestrator: `lib/apiFetch.ts` (401 → wylogowanie także dla zwykłego `fetch`) |
| [E3-06 README](E3-06-readme.md) | 3 | implementer | E3-05 | done | 10 sekcji, komendy sprawdzone `make -n` |
| Przegląd Etapów 2–3 | 3 | reviewer | E3-05 | done | Poprawione (+5 testów regresji): 500 dla kwot `1E30` i > NUMERIC(14,2) w imporcie; podwójny commit importu (blokada `FOR UPDATE`); liczby w `risks` nie były walidowane; wygasłe podglądy importu nie były usuwane |

### Odłożone z przeglądu Etapów 2–3 (do kart Etapu 4)
- Limit dzienny agenta da się przekroczyć równoległymi żądaniami (licznik czyta zapisane przebiegi; brak rezerwacji przed wywołaniem LLM).
- Rozłączenie klienta SSE / „Anuluj” nie przerywa wątku i wywołania modelu; brak keepalive.
- Walidator liczb jest celowo łagodny: liczby całkowite < 100 w tekście nie są sprawdzane, a zaokrąglenia do całości przechodzą; format `1.234,56` daje fałszywy błąd.
- Frontend: zdarzenie SSE `error` jest ignorowane; `noSurplus` porównuje string `"0.00"`.
- `agent/anonymize.scrub` nie jest jeszcze używany (przeznaczony do kategoryzacji AI, F07).

## Etap 4 (część 1): po serii zmian UI/UX

Stan wyjściowy: nawigacja 5 zakładek, edycja transakcji (`PATCH`), karta „Majątek” (`/api/budget/net-worth`), jeden panel Doradcy AI, nowy UI kit. Plan: [`docs/plan.md`](../plan.md), sekcja Etapu 4.

| Karta | Fala | Role | Zależności | Status | Notatka |
|---|---|---|---|---|---|
| [E4-01 Saldo początkowe](E4-01-opening-balance.md) | 1 | implementer + tester | — | done | zrealizowane poza falą: amount/as_of zamiast opening_balance/opening_date, dodany DELETE |
| [E4-02 Transakcje: filtry i paginacja na serwerze](E4-02-transactions-server-filter.md) | 1 | implementer + tester | — | ready | zmiana kształtu odpowiedzi listy |
| [E4-03 Data aktualizacji cen](E4-03-price-timestamps.md) | 1 | implementer + tester | — | ready | `prices_as_of` w podsumowaniu portfela |
| [E4-06 Dostępność UI kit](E4-06-a11y-ui-kit.md) | 1 | implementer + tester | — | ready | tylko `components/ui/**` |
| [E4-04 Historia majątku (wykres)](E4-04-net-worth-history.md) | 2 | implementer + tester | E4-01 | todo | seria tylko dla środków na kontach |
| [E4-05 Testy e2e (Playwright)](E4-05-e2e-playwright.md) | 3 | tester | E4-01, E4-02 | todo | po ustabilizowaniu UI |

Dalsze pozycje Etapu 4 (agent z narzędziami sieciowymi, UC-07, N08/N09, F05/F07, F12–F15) oraz lista „Odłożone z przeglądu Etapów 2–3” wyżej czekają na własne karty.

## Etap 0: specyfikacja

| Zadanie | Status | Notatka |
|---|---|---|
| UC-09..UC-13 (spec-writer) | done | Otwarte kwestie w sekcjach „Uwagi” każdego UC |
| Testowy format CSV | done | [`docs/csv-format.md`](../csv-format.md) |
| Decyzje: monorepo, środowisko lokalne, Ollama | done | `docs/plan.md`, sekcja 0 |
