# Development guide

How to run Coffer locally and test it. The app runs locally only; there is no production deployment. The product from a user's point of view is in the [README](../README.md); the design is in [architecture.md](architecture.md). Commands run from the repository root.

Coffer is a personal-finance app, built at Warsaw University of Technology for *Software Engineering 1* (specification) and *Building AI Agents in .NET* (agent integration; Python agreed with the lecturer).

## 1. Requirements

| Tool | Version | Why | macOS (Homebrew) |
|---|---|---|---|
| Git | any | clone the repo | `brew install git` |
| Docker Desktop | current | Postgres 16 in a container | `brew install --cask docker` |
| uv | current | installs Python 3.12 and backend dependencies | `brew install uv` |
| Node.js + npm | >= 20 | frontend (React, Vite) | `brew install node` |

On Linux use your package manager; on Windows use WSL2 with Docker integration and `make`. Free ports needed: 5432 (Postgres), 8000 (API), 5173 (frontend).

## 2. First run

| Step | Command | What it does |
|---|---|---|
| 1 | `git clone <repo-url> coffer && cd coffer` | get the code |
| 2 | `cp .env.example .env` | optional config; defaults work without it |
| 3 | `make setup` | backend (`uv sync`) and frontend (`npm install`) dependencies |
| 4 | `make db-up` | start Postgres in Docker and wait until ready |
| 5 | `make migrate` | create the schema and system categories (Alembic) |
| 6 | `make seed` | demo account and 3 months of transactions (re-runnable) |
| 7 | `make dev-api` | API on `http://localhost:8000` (terminal 1) |
| 8 | `make dev-web` | frontend on `http://localhost:5173` (terminal 2) |

Log in at <http://localhost:5173> with `demo@coffer.local` / `coffer-demo-2026`. Check: `curl localhost:8000/api/health` returns `ok`.

## 3. Configuration

`COFFER_*` environment variables, from the process or `.env` in the repo root. All optional.

| Variable | Default | Meaning |
|---|---|---|
| `COFFER_DATABASE_URL` | `postgresql+psycopg://coffer:coffer@localhost:5432/coffer` | database URL |
| `COFFER_ALLOWED_ORIGINS` | `["http://localhost:5173","http://localhost:8000"]` | origins allowed for state-changing requests (JSON list or comma-separated; the old `COFFER_ALLOWED_ORIGIN_REGEX` is no longer used and is ignored) |
| `COFFER_SESSION_TTL_DAYS` | `14` | session lifetime |
| `COFFER_COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `COFFER_COOKIE_SAMESITE` | `lax` | `lax` or `strict` |
| `COFFER_PRICE_REFRESH_MINUTES` | `0` | background quote refresh every N minutes (1–1440); `0` = off; manual: `make prices` |

## 4. Troubleshooting

| Symptom | Fix |
|---|---|
| `make db-up` fails | start Docker Desktop and retry |
| "port is already allocated" | free the port (`lsof -i :5432`) or stop the other server |
| clean database | `docker compose down -v`, then `make db-up && make migrate && make seed` |

## 5. Code layout

```text
coffer/
├── CLAUDE.md, .claude/   agent setup (see docs/agents.md)
├── openspec/             specs (source of truth for behaviour) and changes
├── docs/                 architecture, data model, roadmap, history
├── data/fixtures/        fictional test data (csv/testbank-2026-10.csv)
├── docker/               Postgres init (test database)
├── compose.yaml          Postgres 16
├── Makefile              project commands
└── src/
    ├── backend/          Python 3.12, FastAPI, SQLAlchemy, Alembic
    │   ├── alembic/      migrations
    │   ├── tests/        tests, one folder per module
    │   └── coffer/
    │       ├── main.py       FastAPI app, /api/health
    │       ├── core/         config, DB, money (quantize), months, origin check
    │       ├── accounts/     registration, login, sessions, CurrentUser
    │       ├── transactions/ transactions and categories
    │       ├── imports/      CSV import: parser, banks, categorization, de-duplication
    │       ├── budget/       month view, insights, net worth
    │       ├── cash/         opening balance
    │       ├── analytics/    pure functions for totals and shares
    │       ├── profile/      investment profile
    │       ├── portfolio/    holdings and valuation
    │       ├── market/       Yahoo Finance quotes and FX, price job
    │       └── scripts/      dump_openapi, seed_demo, refresh_prices
    └── frontend/         React, TypeScript, Vite
        └── src/
            ├── features/     auth, transactions, import, budget, profile, portfolio
            ├── components/   shared components; ui/ holds the primitives
            ├── api/          HTTP client and types generated from OpenAPI
            ├── lib/          money, months, errors, react-query helpers
            └── i18n/         Polish UI strings (pl.ts)
```

## 6. Tests and quality

| Command | What it does |
|---|---|
| `make check` | everything: lint, backend tests, frontend checks |
| `make lint` | ruff, pyright, import-linter |
| `make test-backend ARGS="tests/accounts"` | backend tests (all without `ARGS`) |
| `make check-web` | tsc, vitest and the frontend build |
| `make openapi` | dump OpenAPI and regenerate TypeScript types |
| `make prices` | fetch quotes into `market_quotes` once |

Backend tests live in `src/backend/tests/<module>`, frontend tests next to the code (`*.test.ts(x)`). Tests use a separate database (`coffer_test` by default); set `COFFER_TEST_DB=coffer_test_<module>` so parallel runs don't wipe each other's data. `yfinance` is mocked in tests, so tests never hit the network.

## 7. Checks before pushing
There is no CI: checks run locally. Before pushing, run:
- `make check` (lint, backend tests, frontend checks);
- `make openapi` if the API changed, and commit `schema.d.ts`;
- the Alembic checks from [data-model.md](data-model.md#testing) if you added a migration.

`make check-web-clean` reinstalls frontend dependencies from the lockfile before checking. Dependencies aren't updated automatically, so bump them deliberately.

## 8. Working with AI agents
See [agents.md](agents.md) and [`CLAUDE.md`](../CLAUDE.md).
