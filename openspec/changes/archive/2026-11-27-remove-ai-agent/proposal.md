# Proposal

## Why

The AI assistant is about 5,000 lines of backend code (plus its tests and UI). It supports four LLM providers, a tool-calling loop, an MCP server and cost tracking, and makes the codebase hard to refactor. We are pausing feature work to simplify the app, and the assistant will be rebuilt from scratch for local LLMs afterwards. Removing it now gives the refactor a smaller, non-AI codebase to work on.

## What Changes

- **BREAKING** Remove the AI assistant: the `coffer.agent` module, every LLM client (Ollama, OpenAI, Gemini, Anthropic), the fallback chain, cost estimates, the action catalog, runs, suggestions and the daily AI limit. Endpoints under `/api/agent/*` are gone.
- **BREAKING** Remove the MCP market server (`coffer.market.mcp_server`, `coffer.market.tools`, the `mcp` dependency, `make mcp-market`) and `GET /api/market/quotes`, which the UI does not call.
- Remove the market functions only the agent used: news, market tips, price history, company profile, symbol search and the Wikipedia summary. Quotes, FX rates, the quote cache and price refresh stay.
- Remove the analytics modules only the agent used: `allocation`, `planning`, `simulate`, `spending`, `market_stats`.
- Remove the LLM and agent settings (`COFFER_LLM_*`, `COFFER_OLLAMA_*`, `COFFER_OPENAI_*`, `COFFER_GEMINI_*`, `COFFER_ANTHROPIC_*`, `COFFER_AGENT_*`).
- **BREAKING** Add a reversible migration that drops `agent_runs`, `suggestions` and `llm_usage_daily`. Existing migrations stay unchanged.
- Keep the investment profile (`GET/PUT /api/profile`) and move its requirement from `ai-agent` to `portfolio`.
- Frontend: remove `features/assistant`, the assistant navigation entry and its i18n strings. The profile section stays.
- Remove the `ai-agent` capability spec, the AI rules in `CLAUDE.md` and `openspec/config.yaml`, the import-linter contract about `coffer.agent`, and agent mentions in `docs/` and `.claude/agents/`. Requirement IDs F31–F37 and N03 become unimplemented until the assistant is rebuilt.

Out of scope:
- Rebuilding the assistant in any form; that will be a later change.
- Refactoring the non-AI modules (`simplify-backend`) and merging their tests (`consolidate-tests`).
- Removing or changing the investment profile.
- The "Works without AI (N08)" requirements in `budget` and `portfolio`. They stay as written and still hold.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `ai-agent`: every requirement is removed; the investment profile requirement (F30) moves to `portfolio`.
- `portfolio`: gains the investment profile requirement (F30), unchanged in behaviour.
- `accounts`: account deletion (N09) no longer lists "agent history" among the deleted data.

## Impact

- Backend: deletes `coffer/agent/`, `coffer/market/{mcp_server,tools}.py`, the agent-only parts of `coffer/market/service.py` and `coffer/market/api.py`, five `coffer/analytics` modules, and the LLM fields in `coffer/core/config.py`. Edits `coffer/main.py`. Adds one Alembic migration.
- Dependencies: `mcp` is removed from `pyproject.toml`; `uv.lock` is updated.
- Tests: deletes `tests/agent/`, the agent parts of `tests/e5/` and `tests/contract_e5/`, and the market MCP, tools and internet tests for the removed functions.
- Frontend: deletes `src/frontend/src/features/assistant/`; edits `App.tsx`, `components/Layout.tsx`, `i18n/pl.ts`, and the API types (`make openapi`).
- Tooling and docs: `Makefile` (`mcp-market`), `pyproject.toml` (import-linter contract), `CLAUDE.md`, `openspec/config.yaml`, `docs/*.md`, `.claude/agents/*.md`, `.env.example` if present.
- Data: run history, suggestions and AI usage counters are lost when the migration runs. This is acceptable because the app runs locally only.
