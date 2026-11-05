# E3-03: Agent: workflow sugestii nadwyżki v2 (narzędzia, walidator, zapis, limity, SSE)

**Fala:** E3/1 · **Zależności:** E3-00; kontrakty E3-01 i E3-02 (implementowane równolegle) · **Role:** implementer + tester · **UC / wymagania:** UC-12, UC-05, F31, F32, F33, N03, N08, N09

## Cel
Pełna sugestia nadwyżki: dane pobierane przez narzędzia z rejestru, odpowiedź w schemacie z uzasadnieniem odwołującym się do danych, walidacja liczb z jedną poprawką, zapis sugestii i śladu przebiegu (`AgentRun`), dzienny limit, postęp na żywo przez SSE, historia sugestii.

## Przeczytaj
- `docs/use-cases/UC-12-surplus-suggestion.md`
- sekcje „Kontrakt” w `docs/tasks/E3-02-agent-tools.md` i `docs/tasks/E3-01-profile.md`
- `src/backend/coffer/agent/{models,llm,schemas,api,testing}.py`, `src/backend/coffer/agent/workflows/surplus.py`, `src/backend/coffer/core/{db,config}.py`
- `src/backend/tests/conftest.py`, istniejące `src/backend/tests/agent/test_surplus*.py` i `test_duration.py` (do przepisania)

## Pliki
- **implementer:** `src/backend/coffer/agent/{api,schemas,service,sse}.py`, `src/backend/coffer/agent/workflows/surplus.py`, `src/backend/coffer/agent/prompts/surplus_v2.md` (v1 zostaje w repo jako historia)
- **tester:** `src/backend/tests/agent/test_surplus.py`, `test_surplus_api.py`, `test_duration.py`, nowe `test_history.py`, `test_runs.py`, `test_sse.py` (pozostałe pliki w `tests/agent/` należą do innych kart)

## Kontrakt

### Workflow (`agent/workflows/surplus.py`)
`run_surplus(db, user_id, month, llm: LLMClient | None, registry: ToolRegistry, on_event: Callable[[AgentEvent], None] = noop) -> SurplusSuggestionOut`

`AgentEvent = {"type": "status", "message": str} | {"type": "summary", "data": MonthSummaryOut} | {"type": "result", "data": SurplusSuggestionOut}` (dict albo dataclass, byle serializowalny do JSON).

1. `status` „Liczę podsumowanie miesiąca…” → narzędzie `get_month_analysis` przez `registry.call` (zapisz `ToolCall`); `MonthSummaryOut` z `budget.service.month_summary` → event `summary`.
2. `surplus == 0` → `ai_status="no_surplus"` (bez LLM).
3. `llm is None` → `unavailable`.
4. Dzienny limit: liczba `AgentRun` użytkownika z bieżącej doby UTC z `attempts > 0` ≥ `settings.agent_daily_limit` → `ai_status="limited"`.
5. `status` „Sprawdzam profil inwestycyjny…” → `get_investment_profile`.
6. `db.commit()` i `db.close()` (połączenie wraca do puli przed wolnym LLM; ta sama sesja posłuży do zapisu).
7. `status` „Asystent analizuje dane…”. Wiadomość `user`: krótki wstęp + JSON listy `{tool, output}` z wywołań narzędzi. `llm.complete(system=prompt v2, messages, response_schema=SuggestionDraft.model_json_schema())`.
8. Parsowanie do `SuggestionDraft` + `validator.validate`. Błąd (zły JSON też) i `attempts < settings.agent_max_attempts` → `status` „Poprawiam odpowiedź…”, dopisz do rozmowy `assistant` (surowa odpowiedź) i `user` („Odpowiedź nie przeszła walidacji: … Popraw ją i odpowiedz ponownie w tym samym formacie JSON.”), ponów.
9. Sukces → zapis `Suggestion` (`data_snapshot` = output `get_month_analysis`, `profile_snapshot` = output profilu, jeśli `available`, inaczej `null`; `disclaimer = DISCLAIMER`) i `AgentRun(status="ok")`. Porażka walidacji → `AgentRun(status="invalid")`, `ai_status="unavailable"`. `LLMUnavailable` → `AgentRun(status="unavailable")`.
10. Każdy przebieg kończący się na krokach 2–9 zapisuje `AgentRun` z: `task="surplus"`, `prompt_version="surplus_v2"`, `tool_calls`, `messages` (system + rozmowa), `raw_outputs`, `validation_errors`, `attempts`, sumą tokenów i `duration_ms` całego przebiegu. Na końcu event `result`.

### Schematy (`agent/schemas.py`)
```
RationaleItemOut { claim, refers_to: "budget"|"profile"|"portfolio", value }
SuggestionOut { id: int, type: str, month: str | None, summary, rationale: list[RationaleItemOut], risks: list[str],
                disclaimer, model, generated_at: datetime, duration_ms: int | None, profile_used: bool }
SurplusSuggestionOut { summary: MonthSummaryOut, ai_status: "ok"|"no_surplus"|"unavailable"|"limited",
                       suggestion: SuggestionOut | None, run_id: int | None }
AgentRunListItem { id, task, status, model, attempts, duration_ms, created_at }
AgentRunOut = AgentRunListItem + { prompt_version, tool_calls, messages, raw_outputs, validation_errors, error, input_tokens, output_tokens }
```
`AgentStatusOut` i `SurplusRequest` bez zmian.

### Endpointy (prefiks `/api/agent`, wszystkie z `CurrentUser`, nigdy 5xx z powodu LLM)
| Metoda i ścieżka | Wynik |
|---|---|
| `POST /surplus` | 200 `SurplusSuggestionOut` (jak dotąd, nowy kształt) |
| `POST /surplus/stream` | 200 `text/event-stream`: `event: status`/`summary`/`result`, `data:` JSON; zawsze kończy się `result`. Workflow w wątku roboczym z **własną sesją z `SessionFactory`** (`coffer.core.db`), zdarzenia przez kolejkę do generatora; nagłówki `Cache-Control: no-cache`, `X-Accel-Buffering: no` |
| `GET /suggestions?limit=20` | 200 `list[SuggestionOut]`, najnowsze pierwsze, tylko własne (`limit` 1–100) |
| `GET /suggestions/{id}` | 200 `SuggestionOut`; 404 „Nie znaleziono sugestii” |
| `GET /runs?limit=20` | 200 `list[AgentRunListItem]` |
| `GET /runs/{id}` | 200 `AgentRunOut`; 404 „Nie znaleziono przebiegu agenta” |

`agent/service.py`: zapytania historii, przebiegów i licznik limitu (filtr po `user_id`).

### Prompt `surplus_v2.md`
Po polsku. Wejście: wyniki narzędzi. Zasady: kopiuj liczby dokładnie z danych (przecinek dozwolony); każdy punkt `rationale` wskazuje źródło (`budget` lub `profile`), a `value` to dokładna wartość z danych; bez profilu (`available=false`) nie odwołuj się do profilu i zaproponuj jego uzupełnienie; nie wymieniaj konkretnych produktów, spółek ani funduszy; `risks`: 1–3 krótkie ryzyka; odpowiedź wyłącznie jako JSON zgodny ze schematem.

## Kryteria akceptacji
- [ ] `make lint` przechodzi
- [ ] testy (tylko `FakeLLM`): sukces z profilem i bez; `refers_to="profile"` bez profilu → poprawka w 2. próbie → `ok`; dwie złe odpowiedzi → `unavailable` + `AgentRun.status="invalid"` z `validation_errors`; `no_surplus`, `llm=None`, `LLMUnavailable`; limit dzienny (`monkeypatch` ustawień); sugestia i przebieg zapisane i widoczne w historii; izolacja (cudza sugestia/przebieg → 404); N03: w `messages` przebiegu brak e-maila i opisów transakcji; SSE: kolejność zdarzeń `status` → `summary` → … → `result`, poprawny `Content-Type`
- [ ] ręcznie (orkiestrator) z `qwen3:8b`: `ai_status="ok"` i wpis w `/runs`
