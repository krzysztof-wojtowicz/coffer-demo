# CI/CD (GitHub Actions)

Repository `krzysztof-wojtowicz/coffer-demo`; files in `.github/`.

## Workflows

**`ci.yml` (CI)** runs on pushes to `main`, PRs to `main`, and manually. A new commit on the same branch cancels the previous run. Permissions: `contents: read`.

| Job | What it does |
|---|---|
| `backend` | Postgres 16 service, `uv sync --locked` with cache, `make lint` (ruff check + format, pyright, import-linter), `pytest` with coverage (`coverage.xml` artifact, 7 days) |
| `frontend` | Node 24 LTS with npm cache, `npm ci`, `tsc --noEmit -p tsconfig.app.json`, `vitest run`, `vite build` |
| `openapi-sync` | `make openapi` (no DB needed) and fail if `src/frontend/src/api/schema.d.ts` changed. Fix: run `make openapi` locally and commit. |

CI has no LLM secrets and sets `COFFER_LLM_PROVIDER=none`; tests use `FakeLLM` and mock `yfinance`, so nothing reaches the network.

**`deploy.yml` (Deploy)** runs via `workflow_run` when CI succeeds for a **push to `main`** (PRs never deploy), or manually.
- **Backend:** `curl -fsS -X POST "$RENDER_DEPLOY_HOOK_URL&ref=<sha>"`, so Render builds exactly the commit CI tested. Without the secret the step is skipped (green).
- **Skipped runs** are normal: GitHub starts Deploy after *every* finished CI on `main`, including failed or cancelled ones.
- **Frontend:** nothing in Actions; Vercel builds every push itself.
- Keep **Auto-Deploy off** in Render (`autoDeploy: false`), or every push is built twice, including ones CI rejected.

**`migrations.yml`** runs Mondays 05:00 UTC, on PRs touching `alembic/` or `models.py`, and manually. On an empty Postgres it checks: exactly one `alembic heads`; `upgrade head`; `alembic check` (no model/migration drift); `downgrade base` + `upgrade head`.

**`dependabot.yml`** opens weekly PRs (Monday) for `uv`, `npm` and GitHub Actions; minor/patch updates are grouped per ecosystem.

## `RENDER_DEPLOY_HOOK_URL` secret
Render → backend service → **Settings → Deploy Hook** → copy (treat like a password) → GitHub → **Settings → Secrets and variables → Actions → New repository secret** named `RENDER_DEPLOY_HOOK_URL`.

## Dependabot policy
- Never merge a Dependabot PR with red CI. If `main` is red, fix it first, then comment `@dependabot rebase`.
- Major bumps of `mcp` and `typescript` are ignored in `dependabot.yml` because they break the build; read the changelog for other majors.
- Merging several PRs in a row cancels earlier CI runs; the last run on `main` is the one that counts.
- No auto-merge on purpose: without required checks, `gh pr merge --auto` would merge immediately.

## Protecting `main` (repo admin)
**Not enabled yet**, which is why some PRs were merged with red CI. Settings → **Rules → Rulesets → New branch ruleset**: name `main`, **Active**, target the default branch; enable **Restrict deletions**, **Block force pushes**, **Require a pull request before merging**, and **Require status checks to pass** (up to date) with `Backend (lint + tests)`, `Frontend (tsc + vitest + build)` and `OpenAPI types in sync`.

## Before pushing
`make check`. `make check-web-clean` reproduces the CI frontend job (clean `npm ci` + the same steps); run `make openapi` if the API changed.
