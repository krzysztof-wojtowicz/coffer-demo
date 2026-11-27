# Backend: Render (free plan)

The FastAPI app runs as a Docker **Web Service** on [Render](https://render.com) (Frankfurt). Config in the repo: `render.yaml` (Blueprint), `src/backend/Dockerfile`, `src/backend/.dockerignore`.

TLS ends at Render's proxy; uvicorn runs with `--proxy-headers --forwarded-allow-ips='*'`, and `COFFER_COOKIE_SECURE=true` marks the cookie `Secure`. On start the container runs:
```
alembic upgrade head && uvicorn coffer.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```
Image: `python:3.12-slim` + `uv sync --frozen --no-dev`, non-root user `coffer`. There is no session secret (session tokens are random and stored in the DB).

## Environment

| Variable | Value | Notes |
|---|---|---|
| `COFFER_DATABASE_URL` | secret | Neon direct URL as-is ([database.md](database.md)) |
| `COFFER_ALLOWED_ORIGINS` | secret | JSON list, e.g. `["https://cofferai.vercel.app"]`; exact `scheme://host[:port]`, lowercase, no trailing `/` (otherwise startup fails). Mutating requests from other origins get 403. |
| `COFFER_ALLOWED_ORIGIN_REGEX` | optional | for Vercel previews (see below) |
| `COFFER_CORS_ENABLED` | `false` | only for direct cross-origin API calls |
| `COFFER_COOKIE_SECURE` / `_SAMESITE` | `true` / `lax` | `none` only for cross-site (requires `Secure`) |
| `COFFER_LLM_PROVIDER` | `gemini` | or `openai`, `anthropic`, `ollama` (remote), `none` |
| `COFFER_GEMINI_MODEL` | `gemini-3.5-flash-lite` | the stable model; `gemini-3.8-flash` often returns 503 |
| `COFFER_LLM_FALLBACKS` | `gemini:gemini-3.8-flash` | backup chain `provider:model,…`; a bad entry stops startup |
| `COFFER_LLM_TIMEOUT_S` | `40` | one model call including retries |
| `COFFER_AGENT_TIMEOUT_S` | `60` | whole action, must be < 110 (Vercel's proxy allows 120 s) |
| `COFFER_AGENT_DAILY_LIMIT` | `20` | model runs per user per day (paid API) |
| `COFFER_PRICE_REFRESH_HOURS` | `0` | keep 0 on free: the instance sleeps |
| `COFFER_PASSWORD_HASH_CONCURRENCY` | `2` | Argon2 memory on 512 MB |
| `COFFER_TRUSTED_PROXY_HOPS` | `0` | don't change until the XFF chain is verified (see release checklist) |
| `COFFER_GEMINI_API_KEY` / `COFFER_OPENAI_API_KEY` / `COFFER_ANTHROPIC_API_KEY` | secrets | for the chosen provider |

Change variables in the service → **Environment** → *Save, rebuild and deploy*.

## LLM in production
Every assistant action calls the model through `coffer/agent/llm.py`; without a model the action returns its rule-based result (`unavailable`), and `no_data` never calls the model.
- **Resilience:** each call has the `COFFER_LLM_TIMEOUT_S` budget. 429/500/502/503/504, network errors and timeouts are retried at most twice with exponential backoff and jitter, honouring `Retry-After`; 400/401/403/404 are not retried. Then the next model in `COFFER_LLM_FALLBACKS` is tried. The whole action shares `COFFER_AGENT_TIMEOUT_S`; when it runs out the result is rule-based with `ai_status: timeout`.
- **SSE keepalive:** the stream sends `: ping` immediately and every 15 s so Vercel's proxy doesn't drop it.
- **Abuse protection** (in process memory): 20 action runs per minute, 200 per day, 2 concurrent per user → 429 with `Retry-After`.
- **Switching provider:** set the provider, key and model in Environment and redeploy. Anthropic as a backup: add `anthropic:claude-haiku-5-5` to `COFFER_LLM_FALLBACKS` and set its key.
- **Ollama in hosting:** a model won't fit Render free (512 MB, no GPU). Options: Ollama Cloud (`COFFER_OLLAMA_URL=https://ollama.com`, `COFFER_OLLAMA_API_KEY` sent as `Authorization: Bearer`); your own GPU machine behind a tunnel, which **must** be protected (Ollama has no auth); or a rented GPU host behind a key-checking proxy.
- **Check:** logged in, `GET /api/agent/status` → `{"provider":"gemini","model":"...","available":true}`. It checks only model metadata (no cost, cached 60 s), so look at *Asystent → Przebiegi agenta* (`/api/agent/runs`) for real outcomes.
- **Typical errors** (Render log `LLM gemini/<model> unavailable (...)`, run `error` field): `404` model not available for the key; `503`/`ReadTimeout` overloaded model (fallback kicks in); `401`/`403` bad key or no credits; `429` provider limit; `ai_status: limited` = `COFFER_AGENT_DAILY_LIMIT` used up; HTTP 429 on `/run` = abuse protection.

## Price job
Quotes are cached in `market_quotes`. Refresh with `make prices` / `python -m coffer.scripts.refresh_prices` (all portfolio symbols plus `<CCY>PLN=X` pairs; per-symbol errors are only reported, exit code 0), or with `COFFER_PRICE_REFRESH_HOURS=N` (1–24), which starts a thread guarded by a DB advisory lock. On Render free keep `0`: the instance sleeps after ~15 min idle. Missing quotes are fetched on demand.

## Origin and CORS
One policy (`coffer/core/origin.py`, `is_allowed_origin`): an origin is trusted when it is exactly in `COFFER_ALLOWED_ORIGINS` or fully matches `COFFER_ALLOWED_ORIGIN_REGEX`. Both mechanisms use it:
- **Origin check (CSRF, always on):** POST/PUT/PATCH/DELETE with an untrusted `Origin` → 403. Requests without `Origin` and safe methods pass.
- **CORS (`COFFER_CORS_ENABLED=true`, off by default):** credentials allowed, explicit origins only (never `*`), the outermost middleware, so preflights are answered before auth and CORS headers reach error and SSE responses.

CORS isn't needed today: the browser talks to Vercel, which rewrites `/api/*` (previews and the Vite dev proxy too). Vercel forwards the browser's `Origin`, so previews still need to pass the Origin check: use the regex, e.g. `https://cofferai-[a-z0-9-]+-<team-slug>\.vercel\.app`. The regex is validated at startup: it must start with `https://` plus a literal host start, use only `[a-z0-9-]`/`\d` classes with quantifiers, end with at least two literal escaped labels (optionally a port), or be exactly `http://localhost` / `http://127\.0\.0\.1`. It may not use `.`, `.*`, `\w`, `|`, groups or `https?://`. Keep it narrow: on a shared domain like `vercel.app`, someone else's project could match.

Calling Render directly from `*.vercel.app` is cross-site (both are public suffixes), so a `Lax` cookie isn't sent; it would need `SameSite=none` + `Secure`, leaving the Origin check as the only CSRF defence, and Safari blocks it anyway. Stay with the Vercel rewrite and `lax`.

## First deploy
1. Sign in at <https://dashboard.render.com> with GitHub and grant access to the repo.
2. **New → Blueprint**, pick the repo and `main`; Render finds `render.yaml` (`coffer-api`).
3. Fill in the `sync: false` secrets (`COFFER_DATABASE_URL`, `COFFER_ALLOWED_ORIGINS`, the LLM key) and **Apply**.
4. Check `curl https://coffer-api-p9ku.onrender.com/api/health` → `{"status":"ok"}`. If Render added a suffix to the name, update the rewrite in `vercel.json`.

## Deploy hook
`autoDeploy` is off: `deploy.yml` deploys after CI passes. Service → **Settings → Deploy Hook** → copy the URL (a secret) → GitHub repo secret **`RENDER_DEPLOY_HOOK_URL`**. Without it, deploy manually: **Manual Deploy → Deploy latest commit**.

## Operations
- **Logs** (live build, migrations, uvicorn) and **Events** (deploy history).
- 403 "Niedozwolone źródło żądania" on login → the frontend domain is missing from `COFFER_ALLOWED_ORIGINS`.
- The session "disappears" → the frontend calls `onrender.com` directly instead of the `/api/*` rewrite.
- **Sleeping:** free instances sleep after 15 min idle and take ~30–60 s to wake. Before a demo, ping `/api/health` (e.g. UptimeRobot every 10 min).

## Testing the image locally
```bash
cd src/backend
docker build -t coffer-api:local .
docker run --rm -p 8080:10000 -e PORT=10000 \
  -e COFFER_DATABASE_URL=postgresql+psycopg://coffer:coffer@host.docker.internal:5432/coffer \
  -e COFFER_LLM_PROVIDER=none coffer-api:local
curl localhost:8080/api/health
```
