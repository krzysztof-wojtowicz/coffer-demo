# E3-02: Agent: rejestr narzędzi, narzędzia „dane użytkownika”, walidator, anonimizacja

**Fala:** E3/1 · **Zależności:** E3-00 · **Role:** implementer + tester · **UC / wymagania:** UC-12, F32, N03, N04

## Cel
Klocki agenta niezależne od konkretnego zadania: rejestr narzędzi (gotowy później do pętli tool use i MCP), dwa narzędzia z danymi użytkownika, walidator sugestii sprawdzający liczby z narzędziami oraz scrubber danych osobowych.

## Przeczytaj
- `src/backend/coffer/budget/service.py` (tylko sygnatura `month_summary`), `src/backend/coffer/analytics/month.py`
- sekcja „Kontrakt” w `docs/tasks/E3-01-profile.md` (`profile.service.get`)
- `src/backend/coffer/profile/models.py`, `src/backend/tests/conftest.py`

## Pliki
- **implementer:** `src/backend/coffer/agent/tools/{__init__,registry,user_data}.py`, `src/backend/coffer/agent/{drafts,validator,anonymize}.py`, `src/backend/coffer/analytics/shares.py`
- **tester:** `src/backend/tests/agent/tools/`

## Kontrakt

### Rejestr (`agent/tools/registry.py`)
```python
@dataclass(frozen=True)
class ToolContext: db: Session; user_id: int          # user_id nigdy nie pochodzi od modelu (F02)
@dataclass(frozen=True)
class Tool: name: str; description: str; input_model: type[BaseModel]
            func: Callable[[ToolContext, Any], BaseModel]   # Any = instancja input_model
@dataclass(frozen=True)
class ToolCall: name: str; arguments: dict[str, Any]; output: dict[str, Any]; duration_ms: int
class UnknownTool(Exception): ...
class ToolArgumentError(Exception): ...
class ToolRegistry:
    def register(self, tool: Tool, toolsets: list[str]) -> None
    def toolset(self, name: str) -> list[Tool]
    def schemas(self, tools: list[Tool]) -> list[dict[str, Any]]
        # format function calling (Ollama/OpenAI): {"type": "function", "function": {"name", "description", "parameters": input_model.model_json_schema()}}
    def call(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> ToolCall
        # walidacja argumentów przez input_model (błąd → ToolArgumentError), output = model_dump(mode="json")
def default_registry() -> ToolRegistry   # zestaw "user_data": oba narzędzia poniżej
```

### Narzędzia (`agent/tools/user_data.py`), opisy po polsku
- `get_month_analysis` (`{month: MonthStr}`) → `{month, income, expenses, balance, surplus, by_category: [{category, expenses, share_pct}]}`. Dane z `budget.service.month_summary`; kwoty jako stringi z 2 miejscami; `share_pct` = udział kategorii w `expenses` jako string z 1 miejscem (np. `"48.6"`), liczony w `coffer/analytics/shares.py`: `category_shares(by_category, total) -> list[Decimal]` (ROUND_HALF_UP do 0.1; przy `total == 0` same zera). Bez nazw kont, opisów, e-maila.
- `get_investment_profile` (`{}`) → `{available: bool, horizon, horizon_label, risk, risk_label, preferred_classes, preferred_classes_labels}`. Etykiety po polsku (np. „długi (powyżej 5 lat)”, „wysoka”, „akcje”); przy braku profilu `available=false` i pozostałe pola `null`/puste.

### Szkic odpowiedzi modelu (`agent/drafts.py`)
```python
class RationaleItem(BaseModel): claim: str (min 1); refers_to: Literal["budget", "profile", "portfolio"]; value: str
class SuggestionDraft(BaseModel): summary: str (min 1); rationale: list[RationaleItem] (1–5); risks: list[str] = [] (max 5)
```

### Walidator (`agent/validator.py`)
`validate(draft: SuggestionDraft, tool_calls: list[ToolCall]) -> list[str]`: lista błędów po polsku (pusta = OK). Błędy trafią z powrotem do modelu, więc mają być konkretne („Liczba 6000 w polu value nie występuje w danych”).
1. `summary` i każde `claim` niepuste po `strip()`.
2. `refers_to="profile"` dozwolone tylko, gdy w `tool_calls` jest `get_investment_profile` z `available=true`; `refers_to="portfolio"` dozwolone tylko, gdy jest wywołanie narzędzia o nazwie zaczynającej się od `get_portfolio` (teraz takiego nie ma, więc zawsze błąd).
3. **Liczby:** `extract_numbers(text) -> list[Decimal]` rozpoznaje `6009,63`, `6 009,63` (spacja lub U+00A0), `6009.63`, `48,6%`, `2026`. Zbiór dozwolonych = liczby wyciągnięte z wszystkich wartości (rekurencyjnie, także stringów) w `output` narzędzi. Każda liczba w `value` musi być dozwolona. W `summary` i `claim` sprawdzaj tylko liczby „kwotowe” (z częścią dziesiętną albo ≥ 100). Liczba całkowita w tekście jest też dozwolona, jeśli równa się dozwolonej liczbie zaokrąglonej do całości (ROUND_HALF_UP) albo obciętej.

### Anonimizacja (`agent/anonymize.py`)
`scrub(text: str) -> str`: IBAN (opcjonalne `PL` + 26 cyfr, dowolne spacje) → `[RACHUNEK]`, e-mail → `[EMAIL]`, ciągi ≥ 6 cyfr (także rozdzielone spacjami w grupach) → `[NUMER]`. Kwoty z przecinkiem (np. `1 234,56`) **nie** są zmieniane.

## Kryteria akceptacji
- [ ] `make lint` przechodzi (`analytics/shares.py` bez SQLAlchemy/FastAPI)
- [ ] testy: rejestr (nieznane narzędzie, złe argumenty, schematy, zestawy); narzędzia na danych z ORM (izolacja użytkowników, brak opisów i e-maila w `output`, profil dostępny i niedostępny); walidator (każda reguła osobno, formaty liczb, zaokrąglenia, `hypothesis` dla `extract_numbers` na liczbach z 2 miejscami w różnych formatach); `scrub` (IBAN z i bez spacji, e-mail, numer karty, kwota zostaje)
