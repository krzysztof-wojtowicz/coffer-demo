# CI/CD (GitHub Actions)

Repozytorium: `krzysztof-wojtowicz/coffer-demo` na GitHubie. Pliki w `.github/`.

## Workflowy

### `ci.yml` (CI)
Uruchamia się przy pushu na `main`, przy każdym pull requeście do `main` i ręcznie. Gdy na tę samą gałąź przyjdzie nowy commit, poprzedni przebieg jest anulowany (`concurrency`). Uprawnienia: tylko `contents: read`.

| Job | Co robi |
|---|---|
| `backend` | Postgres 16 jako service (`coffer`/`coffer`, baza `coffer`; baza `coffer_test` jest zakładana przez `tests/conftest.py`), `uv sync --locked` z cache, `make lint` (ruff check + format, pyright, import-linter), `pytest` z pokryciem (`pytest-cov` doinstalowywany tylko w CI przez `uv run --with`). Raport `coverage.xml` jest artefaktem przebiegu (7 dni). |
| `frontend` | Node 24 LTS z cache npm, `npm ci`, `tsc --noEmit -p tsconfig.app.json`, `vitest run`, `vite build`. Nie potrzebuje `openapi.json` (plik jest w `.gitignore`; frontend korzysta z zacommitowanego `src/api/schema.d.ts`). |
| `openapi-sync` | Uruchamia `make openapi` (bez bazy: zrzut buduje tylko aplikację FastAPI) i failuje, jeśli `src/frontend/src/api/schema.d.ts` się zmienił. Naprawa: `make openapi` lokalnie i commit `schema.d.ts`. |

LLM i rynek: CI nie ma żadnych sekretów LLM i ustawia `COFFER_LLM_PROVIDER=none`. Testy podmieniają klienta LLM (`get_llm_client` + `FakeLLM`), a `yfinance` jest zamockowany w `tests/market/conftest.py` i w testach integracyjnych, więc nic nie wychodzi do sieci.

### `deploy.yml` (Deploy)
Odpala się przez `workflow_run`, gdy workflow **CI** zakończy się sukcesem dla **pusha na `main`** (PR-y nie deployują). Można go też uruchomić ręcznie (Actions → Deploy → Run workflow).

- **Backend (Render):** `curl -fsS -X POST "$RENDER_DEPLOY_HOOK_URL"`. Gdy sekretu nie ma, krok jest pomijany z komunikatem (workflow jest zielony).
- **Frontend (Vercel):** nic nie robimy w Actions. Vercel po podpięciu repo sam buduje każdy push (`main` → produkcja, PR → preview). Root Directory w Vercel: `src/frontend`.

Ważne: jeśli backend deployuje się przez hook po CI, **wyłącz Auto-Deploy w Render** (Service → Settings → Build & Deploy → Auto-Deploy: `No`; w `render.yaml` byłoby to `autoDeploy: false`). Inaczej Render zbuduje każdy push dwa razy, także taki, którego CI nie przepuściło.

### `migrations.yml` (Migrations)
Co poniedziałek o 05:00 UTC, przy PR zmieniających `alembic/` lub `models.py` i ręcznie. Na czystym Postgresie sprawdza:
1. `alembic heads` zwraca dokładnie jedną głowę (inaczej: `alembic merge`),
2. `alembic upgrade head` przechodzi,
3. `alembic check` nie wykrywa rozjazdu modeli i migracji,
4. `downgrade base` + ponowny `upgrade head` (czy downgrade'y działają).

### `dependabot.yml`
Raz w tygodniu (poniedziałek) PR-y z aktualizacjami dla `uv` (`src/backend`), `npm` (`src/frontend`) i GitHub Actions. Aktualizacje minor/patch są grupowane w jeden PR na ekosystem; major przychodzą osobno. Każdy taki PR przechodzi przez CI.

## Sekret `RENDER_DEPLOY_HOOK_URL`
1. Render → serwis backendu → **Settings** → **Deploy Hook** → skopiuj URL (zawiera klucz, traktuj jak hasło).
2. GitHub → repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
3. Name: `RENDER_DEPLOY_HOOK_URL`, Secret: wklejony URL → **Add secret**.

## Branch protection (wymagane CI)
GitHub → **Settings** → **Branches** → **Add branch ruleset** (lub *Add classic branch protection rule*) dla `main`:
- *Require a pull request before merging* (opcjonalnie 1 approval),
- *Require status checks to pass* → dodaj: `Backend (lint + tests)`, `Frontend (tsc + vitest + build)`, `OpenAPI types in sync` (pojawią się na liście po pierwszym przebiegu CI),
- *Require branches to be up to date before merging*,
- *Block force pushes*.

## Badge do README
```markdown
[![CI](https://github.com/krzysztof-wojtowicz/coffer-demo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/krzysztof-wojtowicz/coffer-demo/actions/workflows/ci.yml)
```

## Lokalnie przed pushem
`make check` (lint, testy backendu, front) oraz `make openapi`, jeśli zmieniało się API.
