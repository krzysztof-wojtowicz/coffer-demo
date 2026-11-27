# Design

## Context

Only `coffer/main.py` imports `coffer.agent`, so the core does not depend on it. A few pieces outside the module exist only to serve the agent:

- `coffer.analytics`: `allocation`, `planning`, `simulate`, `spending`, `market_stats`. Budget and portfolio use only `month`, `compare`, `limits`, `net_worth`, `portfolio`, `shares`.
- `coffer.market`: `tools.py`, `mcp_server.py` and the news, tips, history, company profile, symbol search and Wikipedia functions in `service.py`. Portfolio and `refresh_prices` use only quotes, FX and the quote cache.
- `coffer.profile`: only `coffer.agent.tools.user_data` reads it. It stays, see proposal.md.

Tables: `agent_runs`, `suggestions` and `llm_usage_daily` were created in migrations `0003_profile_agent` and `0007_agent_actions`. `investment_profiles` (also from `0003`) stays. The current head is `0009_market_quotes`.

## Goals / Non-Goals

**Goals:**
- Leave no AI code, settings, dependencies, tables, tests, UI or docs behind, and no orphaned helpers that only the agent called.
- Keep `make check` green at the end, with the same behaviour for every non-AI endpoint.

**Non-Goals:**
- Simplifying the code that remains. That belongs to `simplify-backend`, even where the deletion leaves an obvious cleanup next to it.
- Keeping any extension point for the future assistant. It will be designed from scratch.

## Decisions

1. **Drop the tables in a new migration `0010_drop_agent`, not by editing `0003`/`0007`.** Rewriting applied migrations would break existing local databases. `downgrade()` recreates the three tables with their columns, indexes and `ON DELETE CASCADE`, copied from `0003`/`0007`, so the migration stays reversible (CLAUDE.md rule). The dropped data is not restored.

2. **Delete orphans by reachability, not by guessing.** After removing `coffer/agent`, delete every function or module in `analytics` and `market` that nothing in `coffer/` (outside tests) calls. Check this with `grep`, and make sure `make lint` (pyright) is clean. Tests that only covered deleted functions go with them.

3. **Mixed test folders.** `tests/e5/` and `tests/contract_e5/test_tester_agent_engine.py` are agent tests and go entirely. `e5/test_isolation.py::test_limits_isolated` and the session check in `test_new_endpoints_require_session` test non-AI endpoints, so they move to `tests/budget/` and `tests/accounts/` before `e5/` is deleted. `contract_e5/test_tester_analytics_pure.py` and `test_tester_budget_limits.py` keep only their non-agent cases; `consolidate-tests` merges them later.

4. **The `ai-agent` spec is emptied by REMOVED deltas, and its directory is deleted after archiving.** Archiving leaves `openspec/specs/ai-agent/spec.md` with no requirements, so the archive step deletes that directory. The budget spec's Purpose line that mentions the agent's `budget_plan` action is edited directly in `openspec/specs/budget/spec.md`.

5. **Keep the "Works without AI (N08)" requirements.** They still hold, and they will matter again when the assistant returns.

6. **Frontend: delete, don't stub.** Delete `features/assistant` and remove its route, its navigation entry and the `assistant.*` keys in `i18n/pl.ts`. Regenerate the API types with `make openapi` so any leftover use of `/api/agent` fails `tsc`.

## Risks / Trade-offs

- [A helper the agent used is also used, indirectly, by a non-AI path] → Delete in small steps and run `make lint` and the module's tests after each one. Pyright reports any import of a removed symbol.
- [The isolation and account-deletion tests lose coverage when `e5/` goes] → Decision 3 moves the non-AI cases before deleting.
- [Stale docs or agent prompts still describe the assistant] → Task group 5 greps the repo for `agent`, `llm`, `ollama`, `mcp` and `doradca`, and every remaining hit must be intentional: the Claude Code agents in `.claude/` and `docs/agents.md`, which are about the dev workflow, not the app.

## Migration Plan

Run `make migrate` locally. To roll back, `alembic downgrade -1` recreates the empty tables, and `git revert` restores the code.
