# Coffer

Personal-finance web app with an AI assistant (student project, 4 people). Python/FastAPI + PostgreSQL backend, React/TypeScript frontend, LLM via Ollama/OpenAI/Gemini/Anthropic. Production: Vercel + Render + Neon.

## Layout
| Path | What |
|---|---|
| `openspec/specs/` | **Behaviour, source of truth**: `accounts`, `transactions`, `budget`, `portfolio`, `ai-agent` |
| `openspec/changes/` | Planned work (proposal, tasks, delta specs); `openspec list` |
| `docs/` | `architecture.md`, `data-model.md`, `development.md`, `deploy/`, `roadmap.md`, `history.md`, `glossary.md` |
| `src/backend/coffer/` | Modules: `accounts, transactions, imports, budget, cash, portfolio, profile, market, analytics, agent, core` |
| `src/frontend/src/` | `features/*`, `components/ui`, `api/` (generated types), `i18n/pl.ts` |
| `data/fixtures/` | Fictional test data |

## Commands (from the repo root)
- `make setup` · `make db-up` · `make migrate` · `make seed` · `make dev-api` / `make dev-web`
- `make lint` (ruff, pyright, import-linter) · `make check` (everything) · `make check-web` (tsc, vitest, build)
- `COFFER_TEST_DB=coffer_test_<module> make test-backend ARGS="tests/<module>"`: use your own test DB so parallel agents don't collide
- `make openapi`: regenerate `openapi.json` and `schema.d.ts` after API changes · `make prices`: refresh quotes
- `openspec list` · `openspec show <name>` · `openspec validate --all --strict` · `make openspec-skills` (refresh OpenSpec skills; not `openspec update`)

## Hard rules
- **Money:** `Decimal` only, never `float`; round with `coffer.core.money.quantize` (ROUND_HALF_UP). `NUMERIC(14,2)` in the DB; strings in JSON.
- **Totals are computed only in `coffer.analytics`** (pure functions: no DB, no FastAPI). The agent never computes numbers; it interprets them.
- **Module boundaries:** a module uses another only through its `service.py` (or public `analytics` dataclasses). The core never imports `coffer.agent` (enforced by `import-linter`).
- **Module layout:** `coffer/<module>/{api.py, service.py, models.py, schemas.py}`; thin router, logic in `service.py`.
- **Security:** every endpoint except `/api/health` and `/api/auth/{register,login,logout}` requires `CurrentUser`; every query filters by `user_id`; another user's resource → 404.
- **AI privacy:** only aggregates go to the LLM: no e-mail, transaction descriptions or identifiers. A missing LLM must never break the core; every agent action has a rule-based fallback.
- **Migrations:** reversible, one Alembic head, `ON DELETE CASCADE` from `users` on every user table (see `docs/data-model.md` §3).
- **Language:** the UI and user-facing error messages are **Polish**; code, comments, docs and specs are **English**.

## Workflow
1. Any behaviour change starts as an OpenSpec change (`openspec-propose` skill) and is approved by the user.
2. Build it with the `orchestrate` skill: implementer + tester in parallel on disjoint files → integrate → reviewer → docs-writer.
3. Archive with `openspec-archive-change`. Commit only when the user asks.
For small fixes, skip what isn't needed, but still keep the specs true.

## Agents and skills
| Agent | Model | Use for |
|---|---|---|
| `implementer` | sonnet | backend and frontend code for a change |
| `tester` | sonnet | tests from spec scenarios, without reading the implementation |
| `reviewer` | opus | read-only review: correctness, rules, security, privacy |
| `docs-writer` | sonnet | docs/, README, OpenSpec specs and proposals |
| `explorer` | haiku | quick read-only lookups with `file:line` |

Skills: `orchestrate` (team workflow), `openspec-*` (propose, explore, apply, update, sync, archive), `ponytail` (smallest sufficient change), `frontend-design` (UI work).

Agents report in ≤ 15 lines without pasting code. Change only the files you were assigned; other agents may be working in the same tree.
