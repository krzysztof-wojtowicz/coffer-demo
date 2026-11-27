# Release checklist

Use this for every release that changes the database or production configuration. Production: Neon project `dark-hall-98925715`, branch `production`; Render service `coffer-api`; Vercel `cofferai.vercel.app`. The last fully checked release brought production to migration `0005`; the next one must apply `0007`–`0009` (the stage 5 action engine, limits, market quotes).

## 0. Before merging
- [ ] `make check` passes; `make openapi` leaves `schema.d.ts` unchanged.
- [ ] The Migrations workflow is green (one head, `alembic check`, downgrade/upgrade). Locally: `upgrade head`, `check`, `downgrade <previous>`, `upgrade head`.
- [ ] Read every new migration: what locks it takes, whether it can fail on existing data (e.g. unique indexes, CHECKs), what its downgrade loses.

## 1. Neon: check data and create a restore point
1. In the SQL Editor (branch `production`, read-only), check `SELECT version_num FROM alembic_version;` and run any precondition query the new migrations need (e.g. duplicates a new unique index would reject). If a precondition fails, **don't deploy**: the migration aborts, the container won't start, and Render keeps the previous version.
2. Create a restore branch (copy-on-write, free at this size):
   ```bash
   neon branches create --project-id dark-hall-98925715 --parent production --name pre-<rev>-$(date +%Y%m%d)
   ```

## 2. Render: environment before the deploy
- [ ] New variables from `render.yaml`/`config.py` are set (Blueprint values reach a service only on Blueprint sync).
- [ ] `COFFER_ALLOWED_ORIGINS` = `["https://cofferai.vercel.app"]`, exact, lowercase, no trailing `/`.
- [ ] `COFFER_ALLOWED_ORIGIN_REGEX` empty unless previews need POST (strict format, see [backend.md](backend.md#origin-and-cors)).
- [ ] `COFFER_TRUSTED_PROXY_HOPS=0`, `COFFER_PASSWORD_HASH_CONCURRENCY=2`.
- [ ] LLM: `COFFER_GEMINI_MODEL=gemini-3.5-flash-lite`, `COFFER_LLM_FALLBACKS` valid, `COFFER_LLM_TIMEOUT_S=40`, `COFFER_AGENT_TIMEOUT_S` < 110, key set.
- [ ] `COFFER_PRICE_REFRESH_HOURS=0` on the free plan.

Changing variables redeploys the current commit; that's safe when the running code ignores the new variables.

## 3. Deploy order
Vercel deploys `main` right after merge, while the backend is deployed by the hook or manually, so for a few minutes the new frontend may call the old API. To keep that window short:
1. Merge, wait for green CI.
2. The deploy hook runs (or immediately **Manual Deploy → Deploy latest commit**). The container runs `alembic upgrade head`; the old instance serves traffic until the new health check passes.
3. Check the deploy log for `Running upgrade … -> …` and the uvicorn start.
4. For a zero window, hold the Vercel production deployment and **Promote to Production** after step 3.

## 4. Smoke tests
Humans click these on their own accounts; don't create test accounts in production from scripts.
```bash
curl -s https://coffer-api-p9ku.onrender.com/api/health     # {"status":"ok"}
curl -s https://cofferai.vercel.app/api/health               # same, through the rewrite
curl -sI https://cofferai.vercel.app/ | grep -iE 'x-frame|content-security|x-content|referrer|permissions'
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Origin: https://evil.example' \
  -H 'Content-Type: application/json' -d '{}' https://cofferai.vercel.app/api/auth/login   # 403
```
- [ ] Login works; the cookie is `HttpOnly; Secure; SameSite=Lax`; no CSP errors in the console.
- [ ] Summary, transactions, budget, portfolio load.
- [ ] `GET /api/agent/status` (logged in) shows the expected provider and `available: true`.
- [ ] One agent action returns within 60 s with `ai_status: ok`, or a rule-based result (`limited`, `unavailable`, `timeout`) with a Polish message, never a 5xx or a Vercel 504.
- [ ] Render logs show no tracebacks; on a model 503 the fallback is used.
- [ ] Neon: `alembic_version` is the new head. Render memory stays under ~350 MB.

## 5. Rollback
| What | How |
|---|---|
| Frontend | Vercel → Deployments → previous production → **Instant Rollback** |
| Backend, migration failed | Nothing: the deploy failed and Render keeps serving the previous version. Fix and redeploy. |
| Backend, migration succeeded | **Schema first, then code.** The old image runs `alembic upgrade head` and doesn't know the new revision, so it won't start. From a checkout of the new code: `cd src/backend && COFFER_DATABASE_URL='<prod url>' uv run alembic downgrade <previous>`, then Render → Events → previous deploy → **Rollback**. |
| Data | Last resort: restore `production` from the `pre-*` branch (loses writes since it was created). |

## 6. Known risks
- **Per-IP rate limit and X-Forwarded-For (unverified).** Uvicorn takes the leftmost XFF entry. Through Vercel this is the real client IP, but a direct call to `onrender.com` can spoof it, so the per-IP limit can be bypassed (the per-e-mail limit, 10 per 15 min, always holds). A wrong `COFFER_TRUSTED_PROXY_HOPS` could put all users on one counter, so it stays `0` until someone checks the XFF chain in Render logs.
- **Argon2 memory:** new hashes use 19 MiB; old hashes (64 MiB) are rehashed on login. The base process uses ~90–150 MB of the 512 MB limit.
- **In-memory limits** (login, agent abuse protection) reset on restart or sleep and are correct only with 1 instance and 1 worker.
- **Vercel previews:** POST from a preview domain gets 403 until `COFFER_ALLOWED_ORIGIN_REGEX` is set.
