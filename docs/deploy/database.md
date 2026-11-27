# Database: Neon

Production uses a free Postgres on [Neon](https://neon.tech) (the Free plan doesn't expire). Locally we keep using Postgres from `compose.yaml` (`make db-up`).

## What the code already handles
- **Neon URLs work as-is.** The app and Alembic accept `postgres://` and `postgresql://` and switch the scheme to `postgresql+psycopg://`; `?sslmode=require&channel_binding=require` is kept (`coffer/core/db_url.py`, validator in `coffer/core/config.py`).
- **Connection pool** (`coffer/core/db.py`): `pool_pre_ping=True` (drops connections Neon closed while asleep), `pool_size=5`, `max_overflow=5`, `pool_recycle=300`.
- **Pooled endpoint:** if the host contains `-pooler`, psycopg prepared statements are disabled (`prepare_threshold=None`) for PgBouncer transaction mode.
- `make migrate-remote` and `make seed-remote` (below). Nothing seeds production automatically.
- `COFFER_DATABASE_URL` is hidden in `repr(Settings)`; never log it or commit it.

## Direct or pooled?
Use the **direct** URL (`ep-xxx.eu-central-1.aws.neon.tech`): Render runs one instance with at most 10 connections, and its start command runs `alembic upgrade head` with the same URL. Migrations through the pooler (PgBouncer) can break on session features. Switch the app to pooled (`ep-xxx-pooler…`) only with many instances, and keep running migrations with the direct URL.

## Setup
1. Sign up at <https://neon.tech> (GitHub or Google; no card).
2. **Create project**: name `coffer`, Postgres **16**, region **AWS Europe Central 1 (Frankfurt)** (can't be changed later), database `neondb`.
3. **Connect**: branch `main`, role `neondb_owner`, *Connection pooling* **off**; copy the URL. The password is a secret: keep it out of the repo, issues and LLM chats.
4. Migrate from your machine (after `make setup`):
   ```bash
   make migrate-remote COFFER_DATABASE_URL='postgresql://neondb_owner:PASSWORD@ep-...neon.tech/neondb?sslmode=require&channel_binding=require'
   ```
   Quote the URL (`&`, `?`). A ~1 s first connection is Neon waking up. Check with `cd src/backend && COFFER_DATABASE_URL='...' uv run alembic current`. A command-line variable wins over `.env`; never put the Neon URL in `.env`, or `make migrate/dev-api/seed` will hit production.
5. Demo data (optional, deliberately): `make seed-remote CONFIRM=yes COFFER_DATABASE_URL='...'` creates `demo@coffer.local` with the **known** password from `seed_demo.py`. Without `CONFIRM=yes` it refuses.
6. On Render, set `COFFER_DATABASE_URL` to the same direct URL. Each deploy runs migrations, so step 4 is only for the first setup or a sanity check.

## Free plan limits (2026; check <https://neon.tech/pricing>)
About 0.5 GB per project (the demo uses a few MB); monthly compute hours (enough for a small app at 0.25 CU); scale to zero after ~5 min idle (slower first query); a short restore window (hours) instead of full backups. When compute runs out, Neon suspends the DB until month end: the API returns 500 while `/api/health` still works.

## Backup and restore
Before an important change (demo, migration), dump locally (`pg_dump` ≥ server version):
```bash
docker run --rm -v "$PWD:/out" postgres:16 pg_dump '<neon-url>' -Fc -f /out/coffer.dump
docker run --rm -v "$PWD:/out" postgres:16 pg_restore --no-owner -d '<neon-url>' /out/coffer.dump   # into an empty DB
```
`coffer.dump` contains user data: never commit it. Alternative: Neon console → **Branches → Create branch** (instant copy-on-write).

## Reset (deletes ALL data)
- SQL Editor: `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, then `make migrate-remote …` or redeploy Render; or
- `cd src/backend && COFFER_DATABASE_URL='...' uv run alembic downgrade base`, then `make migrate-remote …`; or
- create a new database/project and point Render at the new URL.

## Troubleshooting
| Error | Cause |
|---|---|
| `password authentication failed` | wrong role or password; *Roles → Reset password*, update Render |
| timeout on first connection | the DB is waking up; retry |
| `SSL connection is required` | missing `?sslmode=require` |
| `prepared statement "_pg3_0" does not exist` | a pooled connection without `-pooler` in the host; use the direct URL |
| `ModuleNotFoundError: psycopg2` | an engine built from a raw URL; use `coffer.core.db_url.normalize_database_url` |
