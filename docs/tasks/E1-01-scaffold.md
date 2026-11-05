# E1-01: Szkielet monorepo, modele danych, narzędzia

**Fala:** 0 · **Zależności:** brak · **Role:** implementer (bez testera: weryfikacja przez `make check`) · **Wymagania:** N04, N08 (infrastruktura)

## Cel
Działające monorepo: backend (FastAPI + Postgres + Alembic) i frontend (Vite) uruchamiają się lokalnie, `make check` przechodzi. Wszystkie modele danych Etapu 1 i fikstury testowe istnieją, więc fala 1 może pracować równolegle.

## Przeczytaj
- `CLAUDE.md`
- ta karta (zawiera pełny kontrakt)

## Pliki (implementer)
Wszystko poniżej, poza `src/backend/coffer/<moduł>/{service,schemas}.py` i `tests/<moduł>/`, które należą do fali 1.

```
Makefile  compose.yaml  .env.example  .gitignore (dopisać)  docker/postgres-init.sql
src/backend/pyproject.toml  alembic.ini  alembic/env.py  alembic/versions/0001_initial.py
src/backend/coffer/__init__.py  main.py
src/backend/coffer/core/{__init__,config,db,money,months,origin}.py
src/backend/coffer/accounts/{__init__,models,tokens,deps,api}.py
src/backend/coffer/transactions/{__init__,models,api}.py
src/backend/coffer/budget/{__init__,api}.py
src/backend/coffer/analytics/__init__.py
src/backend/coffer/agent/{__init__,api}.py
src/backend/coffer/scripts/{__init__,dump_openapi}.py
src/backend/tests/{__init__,conftest,test_health}.py
src/frontend/  (projekt Vite react-ts)
```

## Kontrakt

### Narzędzia i komendy
- Backend: `uv`, Python 3.12 (`requires-python = ">=3.12"`, `uv python pin 3.12`). Zależności: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `psycopg[binary]>=3`, `alembic`, `pydantic>=2`, `pydantic-settings`, `argon2-cffi`, `httpx`. Dev: `pytest`, `hypothesis`, `ruff`, `pyright`, `import-linter`.
- `ruff`: line-length 100, reguły `E,F,I,B,UP`. `pyright`: `typeCheckingMode = "standard"`.
- `import-linter` (w `pyproject.toml`), dwa kontrakty `forbidden`:
  1. moduły `coffer.accounts`, `coffer.transactions`, `coffer.budget`, `coffer.analytics`, `coffer.core` nie importują `coffer.agent`;
  2. `coffer.analytics` nie importuje `sqlalchemy`, `fastapi`, `coffer.core.db` (`include_external_packages = true`).
- `compose.yaml`: tylko usługa `db` (`postgres:16`, port `5432`, użytkownik/hasło/baza `coffer`, wolumen `coffer-db`, `docker/postgres-init.sql` tworzy bazę `coffer_test`). Backend, frontend i Ollama działają natywnie na macOS.
- `Makefile` (z katalogu głównego; backend przez `cd src/backend && uv run ...`):
  `setup` (uv sync + npm install), `db-up`, `db-down`, `migrate` (`alembic upgrade head`), `dev-api` (uvicorn `coffer.main:app --reload --port 8000`), `dev-web` (vite), `test-backend` (pytest z `$(ARGS)`), `lint` (ruff check, ruff format --check, pyright, lint-imports), `check-web` (tsc --noEmit, vitest run, vite build), `check` (lint + test-backend + check-web), `openapi` (dump_openapi → `src/frontend/openapi.json` → `openapi-typescript` → `src/frontend/src/api/schema.d.ts`), `seed` (`python -m coffer.scripts.seed_demo`; skrypt powstanie w E1-07).

### Konfiguracja (`coffer/core/config.py`)
`Settings(BaseSettings)`, prefiks env `COFFER_`, plik `.env` w katalogu głównym repo (ścieżka liczona względem `config.py`; brak pliku nie jest błędem). Pola z domyślnymi wartościami:
`database_url = "postgresql+psycopg://coffer:coffer@localhost:5432/coffer"`, `allowed_origins = ["http://localhost:5173", "http://localhost:8000"]`, `session_ttl_days = 14`, `cookie_secure = False`, `llm_provider: Literal["ollama", "none"] = "ollama"`, `ollama_url = "http://localhost:11434"`, `ollama_model = "qwen3:8b"`, `llm_timeout_s = 90`. Funkcja `get_settings()` z `lru_cache`. `.env.example` opisuje wszystkie pola.

### Baza (`coffer/core/db.py`)
`class Base(DeclarativeBase)`, `engine`, `SessionLocal` (sync), zależność FastAPI `get_db() -> Iterator[Session]`, alias `DbSession = Annotated[Session, Depends(get_db)]`.

### Pieniądze i miesiące
- `core/money.py`: `CENT = Decimal("0.01")`; `quantize(value: Decimal) -> Decimal` (ROUND_HALF_UP do groszy); `ZERO = Decimal("0.00")`.
- `core/months.py`: `parse_month(value: str) -> tuple[date, date]` dla formatu `YYYY-MM` zwraca (pierwszy dzień miesiąca, pierwszy dzień następnego miesiąca); niepoprawny format/miesiąc → `ValueError`. Alias `MonthStr = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]`.

### Modele (SQLAlchemy 2, `Mapped[...]`), migracja `0001_initial`
- `accounts.models.User`: `id` int PK, `email` str(254) unique (zapisywany małymi literami), `password_hash` str, `created_at` timestamptz default now.
- `accounts.models.AuthSession` (tabela `auth_sessions`): `id` PK, `user_id` FK → users `ondelete="CASCADE"` index, `token_hash` str(64) unique, `expires_at` timestamptz, `created_at`.
- `transactions.models.Category`: `id` PK, `name` str(50) unique, `in_budget` bool, `is_default` bool. Migracja wstawia kategorie systemowe: Jedzenie, Transport, Mieszkanie, Rachunki, Zdrowie, Rozrywka, Zakupy, Wynagrodzenie, Inne (`is_default=True`), Przelewy własne (`in_budget=False`), Inwestycje (`in_budget=False`). Pozostałe `in_budget=True`, `is_default=False`.
- `transactions.models.Transaction`: `id` PK, `user_id` FK CASCADE index, `date` date, `amount` `Numeric(14,2)`, `currency` str(3) default `"PLN"`, `base_amount` `Numeric(14,2)`, `description` str(500), `category_id` FK → categories, `source` str(10) (`"manual"`/`"import"`), `needs_review` bool default False, `created_at`. Indeks `(user_id, date)`.
- `alembic/env.py` bierze URL z `get_settings().database_url`, chyba że ustawiono `sqlalchemy.url` w konfiguracji Alembica (używane przez testy).

### Uwierzytelnianie: część wspólna
- `accounts/tokens.py`: `new_token() -> str` (`secrets.token_urlsafe(32)`), `hash_token(token: str) -> str` (sha256 hex). Stała `SESSION_COOKIE = "coffer_session"`.
- `accounts/deps.py`: `get_current_user(request, db) -> User` czyta ciasteczko, szuka sesji po `hash_token`, sprawdza `expires_at > now`; brak/wygasła → `HTTPException(401, "Wymagane logowanie")`. Alias `CurrentUser = Annotated[User, Depends(get_current_user)]`.

### Aplikacja (`coffer/main.py`)
`create_app() -> FastAPI` (title „Coffer API”), `app = create_app()`. Rejestruje routery z `accounts.api`, `transactions.api`, `budget.api`, `agent.api` (każdy plik `api.py` w fali 0 definiuje tylko `router = APIRouter(prefix=..., tags=[...])`: `/api/auth`, `/api` (transactions, bo ma `/api/transactions` i `/api/categories`), `/api/budget`, `/api/agent`). `GET /api/health` → `{"status": "ok"}` bez logowania. Middleware z `core/origin.py`: dla POST/PUT/PATCH/DELETE, jeśli nagłówek `Origin` istnieje i nie ma go w `allowed_origins` → 403 `{"detail": "Niedozwolone źródło żądania"}`.

`scripts/dump_openapi.py`: zapisuje `create_app().openapi()` jako JSON do ścieżki z argumentu.

### Testy: fikstury w `tests/conftest.py` (kontrakt dla testerów)
- Baza testowa: nazwa z env `COFFER_TEST_DB` (domyślnie `coffer_test`) na tym samym serwerze. Na starcie sesji: utwórz bazę, jeśli nie istnieje (połączenie z bazą `postgres`, autocommit), uruchom migracje Alembica do `head`, nadpisz `get_db` w aplikacji.
- Po każdym teście: `TRUNCATE users, auth_sessions, transactions RESTART IDENTITY CASCADE` (kategorie zostają).
- Fikstury: `db` (Session), `client` (`TestClient(app)`), `make_user(email="user@example.com", password="haslo12345") -> User` (hash argon2 przez `argon2.PasswordHasher`), `user` (= `make_user()`), `login_as(client, user) -> TestClient` (tworzy `AuthSession` i ustawia ciasteczko), `auth_client` (= `login_as(client, user)`), `other_auth_client` (drugi użytkownik `other@example.com`, osobny `TestClient`), `category_id(name: str) -> int` (fabryka).
- `tests/test_health.py`: `/api/health` zwraca 200.

### Frontend (`src/frontend`)
Vite + React + TypeScript (strict). Zależności: `react-router-dom`, `@tanstack/react-query`, `openapi-fetch`; dev: `openapi-typescript`, `vitest`. `vite.config.ts`: proxy `/api` → `http://localhost:8000`. Pliki: `src/main.tsx` (QueryClientProvider + RouterProvider), `src/api/client.ts` (`createClient<paths>({ baseUrl: "/" , credentials: "include"})`), `src/api/schema.d.ts` (wygenerowany przez `make openapi`), `src/i18n/pl.ts` (obiekt z tekstami), `src/App.tsx` z placeholderem „Coffer”. Skrypty npm: `dev`, `build`, `typecheck`, `test`, `gen:api`. Jeden test vitest (np. że `pl` zawiera klucz `appName`).

## Kryteria akceptacji
- [ ] `make setup && make db-up && make migrate` działa na czystym repo
- [ ] `make check` przechodzi
- [ ] `make openapi` generuje `schema.d.ts`
- [ ] `make dev-api` → `curl localhost:8000/api/health` zwraca `{"status":"ok"}`
- [ ] `lint-imports` ma oba kontrakty i przechodzi

## Poza zakresem
Logika endpointów (fala 1), Docker dla backendu/frontu, CI w GitHub Actions, shadcn/ui, Recharts.
