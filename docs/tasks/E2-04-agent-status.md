# E2-04: Agent: status modelu i czas odpowiedzi

**Fala:** E2/1 · **Zależności:** E1-05 · **Role:** implementer + tester · **UC / wymagania:** UC-12, N08

## Cel
Frontend może przed kliknięciem pokazać, czy lokalny model jest dostępny i jaki to model, a po odpowiedzi ile trwała.

## Przeczytaj
- `src/backend/coffer/agent/{llm,schemas,api}.py`, `src/backend/coffer/agent/testing.py`
- `src/backend/tests/conftest.py`

## Pliki
- **implementer:** `src/backend/coffer/agent/{llm,schemas,api,testing}.py`, `src/backend/coffer/agent/workflows/surplus.py`
- **tester:** `src/backend/tests/agent/test_status.py`, `src/backend/tests/agent/test_duration.py`

## Kontrakt
- `LLMClient` dostaje metodę `status() -> LLMStatus`, gdzie `LLMStatus(available: bool, model: str)`. `OllamaClient.status()`: `GET {base_url}/api/tags` z timeoutem 2 s; `available=True`, gdy odpowiedź 200 i model z konfiguracji jest na liście `models[].name` (porównanie dokładne lub z dopisanym `:latest`). Każdy błąd → `available=False`, bez wyjątku. `FakeLLM(..., available: bool = True)` zwraca `LLMStatus(available, "fake")`.
- `GET /api/agent/status` (`CurrentUser`) → 200 `AgentStatusOut { provider: "ollama" | "none", model: str | None, available: bool }`. Gdy `get_llm_client()` zwraca `None`: `provider="none"`, `model=None`, `available=False`.
- `SuggestionOut` dostaje pole `duration_ms: int` (czas wywołania `llm.complete`, mierzony `time.perf_counter`).
- Endpoint statusu nigdy nie zwraca 5xx.

## Kryteria akceptacji
- [ ] `make lint` przechodzi, istniejące testy agenta przechodzą
- [ ] testy statusu: dostępny, model nieobecny na liście, błąd połączenia, `provider=none`, 401 bez sesji; `duration_ms >= 0` w udanej sugestii
