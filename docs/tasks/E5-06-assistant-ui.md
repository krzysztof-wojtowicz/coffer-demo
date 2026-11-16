# E5-06: Front asystenta: panel akcji, historia sugestii, przebiegi, ślad

**Fala:** E5/2 · **Zależności:** E5-03 · **Role:** frontend (legolas) · **UC / wymagania:** F32, F33, N07, N08; E5-00 §K2–§K4

## Cel
Strona `/assistant` ma jeden panel: wybór akcji z katalogu, formularz parametrów generowany z `ParamSpec`, uruchomienie przez SSE z podglądem kroków na żywo i jeden renderer raportu. Pod nim historia sugestii (filtry, sortowanie, 5 ostatnich + „Wyświetl więcej”) i tabela przebiegów (sortowanie, filtry). Widok śladu to oś kroków z rozwijanymi szczegółami. Stare panele nadwyżki i doradcy znikają.

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (§K2–§K5, D12)
- `src/frontend/src/features/assistant/{AssistantPage,RunDetailPage,queries,parts,sse}.tsx|ts`
- `src/frontend/src/components/ui/{Card,Badge,Button,Select,Field,Input,DatePicker}.tsx`, `src/frontend/src/lib/{apiFetch,errors,money}.ts`
- `src/frontend/src/i18n/pl.ts` (sekcje `assistant`, `portfolio.advisor`)

## Pliki
- **legolas – nowe:** `src/frontend/src/features/assistant/{ActionPanel,ActionForm,ActionReport,RunProgress,SuggestionHistory,RunsTable,RunTimeline,labels}.tsx|ts` + testy `*.test.tsx`
- **legolas – zmiany:** `features/assistant/{AssistantPage,RunDetailPage,queries,parts}.tsx|ts`, `features/portfolio/queries.ts` (usunięcie `useInvestmentAdvice` i typów advice), `lib/errors.ts` (usunięcie `aiStatusMessage` nadwyżki), `i18n/pl.ts`, `api/schema.d.ts` + `openapi.json` (przez `make openapi` na starcie)
- **legolas – usunięcie:** `features/assistant/{AiPanel,AssistantPanel,AssistantPanel.test,AdvisorPanel,AdvisorPanel.vuln.test,state,state.test}.tsx|ts`

## Kontrakt
- Na starcie `make openapi`; typy z `schema.d.ts` (`ActionRunOut`, `ActionReport`, `SuggestionOut`, `AgentRunOut`…), `fetch` przez `apiFetch` dla SSE (jak dziś).
- **ActionPanel:** kafelki/lista akcji z `GET /api/agent/actions` (nazwa, opis, ikonki „dane z Internetu”/„Twoje dane”), status modelu (`/api/agent/status`, istniejący `AiStatusBadge`). Formularz z `params` (`month` → `MonthPicker`, `amount`/`quantity` → pole kwoty z przecinkiem, `select` → `Select`, `symbol`/`text` → `Input`). Wybór akcji i parametry w URL (`/assistant?action=purchase_impact&symbol=VWCE.DE&asset_class=etf`) – deep link dla E5-08. Przycisk „Anuluj” przerywa SSE (`AbortController`).
- **RunProgress:** lista zdarzeń `step` (nazwa narzędzia po polsku z `labels.ts`, czas) i ostatni `status`; zdarzenie `error` pokazuje komunikat (naprawia odłożony błąd ignorowania `error`).
- **ActionReport:** `headline`, siatka `facts` (formatowanie wg `kind`: kwoty `Money`, procenty, daty), `tables` (dostępna tabela HTML), `findings` (z etykietą źródła danych `refers_to`), `recommendations` (symbol, ryzyko 1–5, kwota, link źródła), `risks`, `sources` (tytuł, wydawca, link `target=_blank rel=noopener noreferrer`, „pobrano: <data>”, N07), `disclaimer` zawsze widoczny (F33). Odznaka „AI” / „Reguły” i komunikat dla `ai_status` (`unavailable`, `limited`, `timeout`, `invalid`, `no_data`). Link „Pokaż ślad” do `/assistant/runs/{run_id}`.
- **SuggestionHistory:** `GET /api/agent/suggestions` z filtrami akcja / źródło (AI, reguły) / zakres dat / wyszukiwanie w nagłówku, sortowanie „najnowsze/najstarsze”; domyślnie `limit=5`, „Wyświetl więcej” dociąga kolejne 5 (`offset`), licznik `x z total`. Karta zwięzła (akcja, data, nagłówek, odznaka źródła), rozwinięcie (`details` lub przycisk z `aria-expanded`) pokazuje `ActionReport`. Legacy (`surplus`, `advisor`) z etykietą „Archiwalna: …”.
- **RunsTable:** kolumny data, akcja, status, dostawca (etykiety: `ollama` → „lokalny (Ollama)”, `anthropic` → „Claude”, `gemini` → „Gemini”, `openai` → „OpenAI/zgodny”), model, tokeny we/wy, koszt (USD, „~”, `—` gdy brak), czas, liczba narzędzi; sortowanie klikalnymi nagłówkami (`aria-sort`) po dacie, czasie, koszcie, tokenach; filtry akcja/status/dostawca/daty; paginacja 20.
- **RunDetailPage + RunTimeline:** nagłówek (akcja, status, dostawca, model, tokeny we/wy, koszt szacunkowy, czas całkowity, wersja promptu, data, parametry); oś pionowa kroków z paskiem czasu proporcjonalnym do `duration_ms`, ikoną rodzaju (`tool`/`llm`/`validation`/`fallback`/`limit`/`error`) i statusem; rozwinięcie kroku: argumenty i wynik narzędzia (JSON), dla `llm` tokeny/koszt/surowa odpowiedź, błędy walidacji; sekcja „Prompty” (komunikaty z rolami). Przebieg legacy (`steps` puste) → dotychczasowe sekcje.
- Opcjonalnie: przy `budget_plan` przycisk „Ustaw proponowane limity” (PUT `/api/budget/limits/{id}` dla wierszy tabeli `proposed_limits`, potwierdzenie `ConfirmDialog`).

## Testy (legolas, vitest, mock `fetch`)
- Formularz z `ParamSpec` (w tym walidacja kwoty), SSE: `step` → lista kroków, `result` → raport, `error` → komunikat, anulowanie.
- Raport: fallback z odznaką „Reguły”, źródła z datą pobrania, zastrzeżenie zawsze obecne.
- Historia: 5 elementów, „Wyświetl więcej” wysyła `offset=5`, zmiana filtra resetuje listę; tabela: zmiana sortowania zmienia parametry zapytania; oś kroków rozwija szczegóły.

## Kryteria akceptacji
- [ ] `make check-web` (tsc, vitest, build); `make openapi` bez różnic po regeneracji
- [ ] `grep -rn "surplus\|AdvisorPanel\|investment/advice" src/frontend/src` → tylko etykiety legacy i nadwyżka budżetowa (F11)
- [ ] dostępność: tabele z `<th scope>`, `aria-sort`, rozwijane elementy obsługiwane klawiaturą

## Poza zakresem
UI budżetu i portfela (E5-08), e2e Playwright.
