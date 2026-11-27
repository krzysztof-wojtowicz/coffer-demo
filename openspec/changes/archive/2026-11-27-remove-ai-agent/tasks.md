# Tasks

Owners: groups 1–4 are **implementer** work (one agent, in order, since they touch the same files). Group 5 is **docs-writer**. The **tester** owns the test moves in 1.1, which run before the implementer deletes `tests/e5/`. Disjoint files: the tester writes only under `src/backend/tests/{accounts,budget}/`.

## 1. Keep the non-AI test coverage (tester)

- [x] 1.1 Move the non-agent assertions from `tests/e5/test_isolation.py` (limit isolation; the session check for budget, cash, portfolio and profile endpoints) into `tests/budget/` and `tests/accounts/`. Verify that `COFFER_TEST_DB=coffer_test_budget make test-backend ARGS="tests/budget tests/accounts"` passes.
- [x] 1.2 In `tests/contract_e5/test_tester_analytics_pure.py` and `test_tester_budget_limits.py`, delete only the cases that import removed analytics or agent code. Verify that both files pass on their own.

## 2. Backend removal (implementer)

- [x] 2.1 Delete `coffer/agent/`, remove its router from `coffer/main.py`, and delete `tests/agent/`, `tests/e5/` and `tests/contract_e5/test_tester_agent_engine.py`. Verify the app starts (`make dev-api`; `GET /api/health` → 200).
- [x] 2.2 Delete `coffer/market/mcp_server.py`, `coffer/market/tools.py`, `GET /api/market/quotes` with its schemas, and the `market` router if it ends up empty. Remove the `mcp` dependency (update `uv.lock` with `uv lock`) and the `mcp-market` target from the `Makefile`. Delete `tests/market/test_mcp_server.py` and `tests/market/test_tools.py`. Verify that `make lint` passes.
- [x] 2.3 Delete the market functions and dataclasses nothing calls any more (news, tips, history, company profile, symbol search, Wikipedia, instrument universe) and their tests (`tests/market/test_internet.py` and the matching cases elsewhere). Verify with a grep that every remaining public function in `coffer/market/service.py` is called from `coffer/`, and that `COFFER_TEST_DB=coffer_test_market make test-backend ARGS="tests/market tests/portfolio tests/scripts"` passes.
- [x] 2.4 Delete `coffer/analytics/{allocation,planning,simulate,spending,market_stats}.py` and their tests. Verify that `make lint` and `make test-backend ARGS="tests/analytics tests/budget"` pass.
- [x] 2.5 Remove the LLM and agent settings and the `llm_fallbacks` parsing and validation from `coffer/core/config.py`, the matching variables from `.env.example`, and the "Core modules do not import the agent" import-linter contract from `pyproject.toml`. Verify that `make lint` passes and `grep -ri "llm\|ollama\|openai\|gemini\|anthropic" src/backend/coffer` returns nothing.

## 3. Database (implementer)

- [x] 3.1 Add migration `0010_drop_agent` that drops `suggestions`, `agent_runs` and `llm_usage_daily`. Its `downgrade()` recreates them as created in `0003` and `0007`. Verify with `make migrate`, then `alembic downgrade -1` and `alembic upgrade head` against a test DB, and confirm that `tests/test_migrations_e5.py` (with the agent table checks removed) passes with one head.

## 4. Frontend (implementer)

- [x] 4.1 Delete `src/frontend/src/features/assistant/`, and remove its route in `App.tsx`, its entry in `components/Layout.tsx` and the assistant strings in `i18n/pl.ts`. Run `make openapi`. Verify that `make check-web` passes (tsc, vitest, build) and that the profile section on the account page still renders.

## 5. Specs and docs (docs-writer)

- [x] 5.1 Update `CLAUDE.md` (remove the AI privacy rule, the agent from the module list, the totals rule's "the agent never computes numbers", and the LLM in the stack line) and `openspec/config.yaml` `context`. Verify with a grep that neither file mentions an LLM provider or `coffer.agent`.
- [x] 5.2 Delete `docs/mcp-market.md`. Remove the agent sections and references from `docs/architecture.md`, `data-model.md`, `development.md`, `glossary.md`, `roadmap.md`, `vision.md` and `README.md`, recording in `docs/roadmap.md` that the assistant will be rebuilt for local LLMs. Edit the `budget` spec Purpose so it no longer refers to the `budget_plan` action, and the `portfolio` spec Purpose so it no longer refers to `docs/mcp-market.md`. Verify that `grep -rli "doradca\|coffer.agent\|mcp" docs README.md openspec/specs` returns only the intended hits.

## 6. Verification

- [x] 6.1 Run `make lint`, `make test-backend`, `make check-web`, `make openapi` (no diff afterwards) and `openspec validate remove-ai-agent --strict`. All must pass.

## Workflow follow-up

- Review with the `reviewer` agent (rules, account deletion still cascades, no orphaned code).
- Archive with `openspec-archive-change`, then delete the empty `openspec/specs/ai-agent/` directory.
