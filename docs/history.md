# Project history

A squashed record of the finished work (formerly task cards `docs/tasks/E*-*.md`, removed). Each stage ran as waves of cards with disjoint files, an implementer and an independent tester per card, and one review per wave. New work goes through OpenSpec changes instead (see [agents.md](agents.md)).

## Stage 0: specification (Nov 2026)
Vision, requirements (F/N), glossary and use cases UC-01…UC-13 (now in [`openspec/specs/`](../openspec/specs)); the fictional CSV format ([csv-format.md](csv-format.md)). Decisions: monorepo, local-first development, Ollama as the default LLM.

## Stage 1: end-to-end skeleton
Shipped: monorepo scaffold (`uv`, Vite, Compose with Postgres, `make check`, `import-linter`), accounts with sessions and an Origin check, transactions, `analytics` month summary and surplus, a minimal surplus-suggestion workflow with FakeLLM and fallback, the frontend, and demo seed data (94 transactions over 4 months).
Decisions: constant-time response for unknown e-mails (dummy hash); a positive amount is always income; registration logs the user in; a comma in amounts is accepted as a decimal separator; TypeScript pinned to ~5.9 for `openapi-typescript`.
Review fixes: 500s for months outside 1900–2099 and amounts like `1e30`; the DB connection held during the LLM call.

## Stage 2: CSV import, Tailwind, assistant panel
Shipped: backend CSV import with preview drafts, de-duplication and keyword categorization (`transactions.service.bulk_create`, 0-based row indexes); Tailwind and a month picker; AI model status (`duration_ms`); the import page (`fetch` + `FormData`); the assistant panel (`fetch` with `AbortController`, types from `schema.d.ts`).

## Stage 3: AI agent (M)
Foundation: `InvestmentProfile`, `AgentRun`, `Suggestion` (migration `0003`); global 401 handling (`lib/queryClient.ts`, `lib/apiFetch.ts`).
Shipped: investment profile; agent tools, number validator and anonymizer; surplus workflow v2 with SSE; dark theme with semantic tokens; frontend for profile, SSE, history and trace; README.
Decisions: investment horizon buckets are up to 2 years / 2–5 / over 5 years.
Review fixes: 500s for `1E30` and amounts over NUMERIC(14,2) in import; double import commit (`FOR UPDATE` lock); numbers in `risks` not validated; expired import drafts not removed.

## Stage 4a: after the UI/UX overhaul
State: 5 tabs (Summary, Transactions, Portfolio, AI Advisor, Account), inline transaction edit (`PATCH`), the net-worth card, a new UI kit, and theme switching with a contrast guard.
Shipped: opening balance (`opening_balances`, `0006`, implemented as `amount`/`as_of` with a DELETE endpoint); price timestamps (merged into stage 5).
Still open, now OpenSpec changes: server-side transaction filtering, net-worth history chart, Playwright e2e, UI-kit accessibility.

## Stage 5: one agent-action engine, category limits, price job
The architecture decisions were:
- Replace the separate surplus workflow and portfolio advisor with **one action engine** (`agent/runner.py`) and a catalog of six actions.
- Tools are called through a **structured-output JSON protocol** so every provider works the same.
- **Code computes the numbers and the model writes only the narrative.** Every action has a rule-based fallback in the same report schema.
- One run endpoint. A missing LLM, a limit, a timeout or an invalid answer returns **200 with the rule-based result**.
- An atomic daily limit (`llm_usage_daily`, `reserve_run`) and a richer trace (`steps`, `provider`, `cost_usd`).
- Market data from yfinance and Wikipedia without keys. Each item has `fetched_at` and `source_url`.
- Quotes cached in `market_quotes` and refreshed by `make prices` or an optional thread.
- Category limits and month comparisons as pure `analytics` functions.
- Backend changes don't run `make openapi`; types are regenerated once per wave to avoid conflicts.

Shipped:
- migrations `0007`–`0009`
- month comparisons and limits (F12–F15)
- the action engine and API
- market data and the price job (`prices_as_of`)
- the `savings_analysis`, `purchase_impact`, `budget_plan`, `investment_ideas` and `company_research` actions (`portfolio_review` is the reference action)
- the assistant UI (action panel, history, runs, trace timeline)
- the budget, limits and price-date UI
- import gaps: module boundaries, learning from the user's own categorizations, and the N05 200-row test
- cross-cutting tests: privacy, isolation, no network, trace, concurrent limits, N08 for all six actions
- documentation

## After stage 5
A security sweep found and fixed vulnerabilities, each one with an exploit test, and a frontend CI fix landed. A gold-finance theme with a light/dark/system switch was added.

## Deployment removed (Nov 2026)
Until the refactoring, the app ran on free plans: the SPA on Vercel, which rewrote `/api/*` to the API; the API on Render (Docker, Frankfurt), deployed by a GitHub Actions hook after CI; and Postgres on Neon. The production setup didn't work reliably, so it was removed to keep development local-only. That covered `render.yaml`, `vercel.json`, the backend `Dockerfile`, the `deploy.yml` workflow, Neon config, `make migrate-remote`/`seed-remote` and `docs/deploy/`. GitHub automation was removed as well: the CI and migration-check workflows and Dependabot (`.github/`), with Actions disabled on the repository. Checks now run locally (`make check`). Everything can be restored from git history if hosting comes back.

## AI assistant removed (Nov 2026)
To simplify the refactoring, the AI assistant was removed (change `remove-ai-agent`): the `coffer.agent` module, all LLM clients (Ollama, OpenAI, Gemini, Anthropic), the MCP market server, `/api/agent/*`, `GET /api/market/quotes`, the assistant tab, and the tables `agent_runs`, `suggestions` and `llm_usage_daily` (dropped by a new migration). The investment profile, quotes, FX and the price job stay. Stages 2, 3 and 5 above describe the assistant as it was. It will be rebuilt for local LLMs after the refactor (see the [roadmap](roadmap.md)).

## Open follow-ups from reviews
- Expired `auth_sessions` and abandoned import drafts are never purged (see [data-model.md](data-model.md) §2h).
- `OriginMiddleware` lets requests without an `Origin` header through on purpose, relying on SameSite=Lax. This should be revisited if the app is hosted again.
