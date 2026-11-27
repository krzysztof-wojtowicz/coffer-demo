# Development guide

How to run Coffer locally, configure the AI assistant, and test. The app runs locally only; there is no production deployment. The product from a user's point of view is in the [README](../README.md); the design is in [architecture.md](architecture.md). Commands run from the repository root.

Coffer is a personal-finance app with an AI assistant, built at Warsaw University of Technology for *Software Engineering 1* (specification) and *Building AI Agents in .NET* (agent integration; Python agreed with the lecturer).

## 1. Requirements

| Tool | Version | Why | macOS (Homebrew) |
|---|---|---|---|
| Git | any | clone the repo | `brew install git` |
| Docker Desktop | current | Postgres 16 in a container | `brew install --cask docker` |
| uv | current | installs Python 3.12 and backend dependencies | `brew install uv` |
| Node.js + npm | >= 20 | frontend (React, Vite) | `brew install node` |
| Ollama | current | local AI model (optional) | `brew install --cask ollama` |

Model: `ollama pull qwen3:8b` (about 5 GB; 16 GB RAM recommended). Smaller: `ollama pull qwen3:4b` and `COFFER_OLLAMA_MODEL=qwen3:4b`. On Linux use your package manager; on Windows use WSL2 with Docker integration and `make`. Free ports needed: 5432 (Postgres), 8000 (API), 5173 (frontend), 11434 (Ollama).

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

Log in at <http://localhost:5173> with `demo@coffer.local` / `coffer-demo-2026`. Check: `curl localhost:8000/api/health` returns `ok`, and the assistant panel shows the model status ("`<model>` · dostępny", "Model niedostępny" or "AI wyłączone").

## 3. Configuration

`COFFER_*` environment variables, from the process or `.env` in the repo root. All optional.

| Variable | Default | Meaning |
|---|---|---|
| `COFFER_DATABASE_URL` | `postgresql+psycopg://coffer:coffer@localhost:5432/coffer` | database URL |
| `COFFER_ALLOWED_ORIGINS` | `["http://localhost:5173","http://localhost:8000"]` | origins allowed for state-changing requests (JSON list) |
| `COFFER_SESSION_TTL_DAYS` | `14` | session lifetime |
| `COFFER_COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `COFFER_LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `gemini`, `anthropic` or `none` |
| `COFFER_OLLAMA_URL` / `COFFER_OLLAMA_MODEL` | `http://localhost:11434` / `qwen3:8b` | Ollama server and model |
| `COFFER_OPENAI_API_KEY` / `_MODEL` / `_BASE_URL` | – / `gpt-4o-mini` / `https://api.openai.com/v1` | OpenAI or any OpenAI-compatible API |
| `COFFER_GEMINI_API_KEY` / `_MODEL` | – / `gemini-3.5-flash-lite` | Google Gemini |
| `COFFER_ANTHROPIC_API_KEY` / `_MODEL` | – / `claude-sonnet-5-5` | Anthropic Claude |
| `COFFER_LLM_FALLBACKS` | – | backup models `provider:model,…`, e.g. `gemini:gemini-3.8-flash` |
| `COFFER_LLM_TIMEOUT_S` | `90` | one model request |
| `COFFER_AGENT_TIMEOUT_S` | `60` | whole action budget, < 110 |
| `COFFER_AGENT_DAILY_LIMIT` | `50` | model runs per user per day; then actions return the rule-based result |
| `COFFER_AGENT_MAX_ATTEMPTS` | `2` | 1 call + 1 fix after a validation error |
| `COFFER_PRICE_REFRESH_HOURS` | `0` | background quote refresh every N hours (1–24); `0` = off; manual: `make prices` |

- **Disable AI:** `COFFER_LLM_PROVIDER=none` and restart `make dev-api`. Everything else keeps working.
- **Cloud models:** set the provider, key and model in `.env`, then restart. For Claude, create a key at [console.anthropic.com](https://console.anthropic.com) (prepaid credits are required; without them every call fails and the assistant shows "niedostępny"). Without a key the status is "Model niedostępny" and the rest of the app is unaffected. With a cloud provider the aggregates leave your machine and are processed under the provider's terms.

### LLM clients
`src/backend/coffer/agent/llm.py` uses only `httpx` (no provider SDKs). Every provider implements the `LLMClient` protocol: `status()` and `complete(system, messages, response_schema) -> LLMResponse` (content, model, provider, tokens). `get_llm_client()` picks the client from `COFFER_LLM_PROVIDER`, wrapped in `FallbackLLM` when fallbacks are configured.
- **Structured output:** Ollama `format`; OpenAI `response_format: json_schema` (non-strict); Gemini `responseSchema` (`gemini_schema()` inlines `$ref`, maps nullable types, drops unsupported keywords); Claude Messages API with `output_config.format` (`anthropic_schema()` adds `additionalProperties: false` and drops numeric/length constraints), reading only `text` blocks.
- **Errors:** network errors, timeouts, non-200 statuses and empty/invalid answers become `LLMUnavailable`; the action then returns its rule-based result. Cloud `status()` makes no paid call; it only checks a key is set.
- **Secrets:** keys come only from config, have `repr=False`, and go in headers (`x-goog-api-key`, `x-api-key`), never in URLs, logs or responses.

## 4. Troubleshooting

| Symptom | Fix |
|---|---|
| `make db-up` fails | start Docker Desktop and retry |
| "port is already allocated" | free the port (`lsof -i :5432`) or stop the other server |
| "Model niedostępny" | start Ollama (`ollama serve`), check `ollama list`, `ollama pull qwen3:8b`, `COFFER_OLLAMA_URL` |
| slow first answer | the first call loads the model; use `qwen3:4b` or raise `COFFER_LLM_TIMEOUT_S` |
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
    │       ├── budget/       month view, limits, insights, net worth
    │       ├── cash/         opening balance
    │       ├── analytics/    pure functions for totals and shares
    │       ├── profile/      investment profile
    │       ├── portfolio/    holdings and valuation
    │       ├── market/       Yahoo Finance data, price job, MCP server
    │       ├── agent/        AI assistant: runner, guard, trace, llm, validator,
    │       │                 actions/ (6), tools/ (22), prompts/ (<action>_v1.md)
    │       └── scripts/      dump_openapi, seed_demo, refresh_prices
    └── frontend/         React, TypeScript, Vite
        └── src/
            ├── features/     auth, transactions, import, budget, profile, portfolio, assistant
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

Backend tests live in `src/backend/tests/<module>`, frontend tests next to the code (`*.test.ts(x)`). Tests use a separate database (`coffer_test` by default); set `COFFER_TEST_DB=coffer_test_<module>` so parallel runs don't wipe each other's data. The LLM is replaced with `FakeLLM` in tests and `yfinance` is mocked, so tests never hit the network.

## 7. Checks before pushing
There is no CI: checks run locally. Before pushing, run:
- `make check` (lint, backend tests, frontend checks);
- `make openapi` if the API changed, and commit `schema.d.ts`;
- the Alembic checks from [data-model.md](data-model.md#testing) if you added a migration.

`make check-web-clean` reinstalls frontend dependencies from the lockfile before checking. Dependencies aren't updated automatically, so bump them deliberately.

## 8. Working with AI agents
See [agents.md](agents.md) and [`CLAUDE.md`](../CLAUDE.md).
