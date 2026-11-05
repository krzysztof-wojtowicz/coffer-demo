# E1-05: Agent: klient LLM (Ollama) i sugestia nadwyżki

**Fala:** 1 · **Zależności:** E1-01 (do testów API także E1-04) · **Role:** implementer + tester · **UC / wymagania:** UC-12, F31, F32 (częściowo), F33, N03, N08

## Cel
Pierwsze prawdziwe wywołanie LLM: na żądanie system liczy podsumowanie miesiąca, a lokalny model (Ollama) tworzy krótką sugestię wykorzystania nadwyżki z uzasadnieniem i zastrzeżeniem. Bez modelu reszta działa.

## Przeczytaj
- `docs/use-cases/UC-12-surplus-suggestion.md`
- `src/backend/coffer/core/config.py` (pola `llm_*`, `ollama_*`)
- sekcja „Kontrakt” w `docs/tasks/E1-04-budget-analytics.md` (`MonthSummary`, `budget.service.month_summary`, `MonthSummaryOut`)
- `src/backend/tests/conftest.py`

## Pliki
- **implementer:** `src/backend/coffer/agent/{api,llm,schemas}.py`, `src/backend/coffer/agent/workflows/{__init__,surplus}.py`, `src/backend/coffer/agent/prompts/surplus_v1.md`, `src/backend/coffer/agent/testing.py` (`FakeLLM`)
- **tester:** `src/backend/tests/agent/`

## Kontrakt

### Warstwa LLM (`agent/llm.py`)
```python
@dataclass(frozen=True)
class LLMMessage: role: Literal["user", "assistant"]; content: str
@dataclass(frozen=True)
class LLMResponse: content: str; model: str; input_tokens: int | None; output_tokens: int | None
class LLMUnavailable(Exception): ...
class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[LLMMessage],
                 response_schema: dict[str, Any] | None = None) -> LLMResponse: ...
class OllamaClient:  # implementuje LLMClient
    def __init__(self, base_url: str, model: str, timeout_s: float): ...
def get_llm_client() -> LLMClient | None   # zależność FastAPI; settings.llm_provider == "none" → None
```
- `OllamaClient` używa `httpx`: `POST {base_url}/api/chat` z `{"model", "messages": [system, ...], "stream": false, "format": response_schema, "think": false, "options": {"temperature": 0.2}}`. Błąd połączenia, timeout, status ≠ 200 → `LLMUnavailable`. Tokeny z `prompt_eval_count` / `eval_count`.
- `agent/testing.py`: `FakeLLM(responses: list[str | Exception])` zwraca kolejne odpowiedzi (wyjątek jest rzucany), zapisuje wywołania w `self.calls: list[dict]` (`system`, `messages`, `response_schema`). Model: `"fake"`.

### Workflow (`agent/workflows/surplus.py`)
`suggest_surplus(db, user_id: int, month: str, llm: LLMClient | None) -> SurplusSuggestionOut`
1. `summary = budget.service.month_summary(db, user_id, month)`.
2. `summary.surplus == 0` → `ai_status="no_surplus"`, bez wywołania LLM.
3. `llm is None` → `ai_status="unavailable"`.
4. Wiadomość do modelu: JSON z miesiącem, `income`, `expenses`, `surplus` i `by_category` (nazwa kategorii + kwota) jako stringi. **Nic więcej** (N03): bez e-maila, `user_id`, opisów transakcji.
5. System prompt z `prompts/surplus_v1.md` (po polsku: asystent informacyjny, nie doradca; ma odnieść się do podanych liczb, nie wymyślać nowych, odpowiedzieć po polsku, 2–4 zdania + 1–3 punkty uzasadnienia).
6. `response_schema` = JSON Schema `SuggestionDraft`.
7. Odpowiedź parsuj jako `SuggestionDraft`. Niepoprawny JSON, pusta `rationale` lub `LLMUnavailable` → `ai_status="unavailable"` (bez ponownej próby w E1).
8. Sukces → `ai_status="ok"`, `suggestion` z `disclaimer = DISCLAIMER`, `model`, `generated_at` (UTC).

### Schematy (`agent/schemas.py`)
```python
DISCLAIMER = "To jest sugestia informacyjna, a nie porada inwestycyjna. Decyzję podejmujesz samodzielnie."
SuggestionDraft { summary: str (min 1), rationale: list[str] (min 1) }
SuggestionOut  { summary: str, rationale: list[str], disclaimer: str, model: str, generated_at: datetime }
SurplusRequest { month: MonthStr }
SurplusSuggestionOut { summary: MonthSummaryOut, ai_status: Literal["ok", "no_surplus", "unavailable"],
                       suggestion: SuggestionOut | None }
```

### Endpoint
`POST /api/agent/surplus` (`CurrentUser`), body `SurplusRequest` → 200 `SurplusSuggestionOut`. LLM wstrzykiwany przez `Depends(get_llm_client)` (testy nadpisują go `FakeLLM`). Endpoint **nigdy** nie zwraca 5xx z powodu LLM.

### Testy
Tylko `FakeLLM` (żadnych połączeń z Ollamą). Przypadki: sukces; brak nadwyżki (LLM nie wywołany); `llm=None`; `LLMUnavailable`; zły JSON; pusta `rationale`; **N03**: treść wiadomości do LLM nie zawiera e-maila użytkownika ani opisów transakcji (utwórz transakcję z opisem np. `"Przelew Jan Kowalski PL61109010140000071219812874"`). Test `OllamaClient` przez `httpx.MockTransport` lub nadpisanie transportu: poprawne body żądania, mapowanie błędu na `LLMUnavailable`.

## Kryteria akceptacji
- [ ] `make lint` przechodzi (rdzeń nie importuje `coffer.agent`)
- [ ] testy testera przechodzą
- [ ] ręcznie (orkiestrator): z działającą Ollamą (`qwen3:8b`) endpoint zwraca `ai_status="ok"`

## Poza zakresem
SSE, zapis `Suggestion`/`AgentRun`, walidator liczb, profil inwestycyjny, portfel (Etap 3).
