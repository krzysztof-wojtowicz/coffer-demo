BACKEND = cd src/backend && uv run
FRONTEND = cd src/frontend

.PHONY: setup db-up db-down migrate dev-api dev-web test-backend lint check-web check-web-clean check openapi seed mcp-market migrate-remote seed-remote

setup:
	cd src/backend && uv sync
	cd src/frontend && npm install

db-up:
	docker compose up -d --wait db

db-down:
	docker compose down

migrate:
	$(BACKEND) alembic upgrade head

# Remote DB (e.g. Neon): make migrate-remote COFFER_DATABASE_URL='postgresql://...'
REMOTE_GUARD = @test -n "$(COFFER_DATABASE_URL)" || { echo "Ustaw COFFER_DATABASE_URL (connection string z Neon)"; exit 1; }

migrate-remote:
	$(REMOTE_GUARD)
	@cd src/backend && COFFER_DATABASE_URL='$(COFFER_DATABASE_URL)' uv run alembic upgrade head

# Demo data on a remote DB: only on explicit request (creates a user with a public password)
seed-remote:
	$(REMOTE_GUARD)
	@test "$(CONFIRM)" = "yes" || { echo "Seed zdalnej bazy: dodaj CONFIRM=yes (tworzy konto demo ze znanym hasłem)"; exit 1; }
	@cd src/backend && COFFER_DATABASE_URL='$(COFFER_DATABASE_URL)' uv run python -m coffer.scripts.seed_demo

dev-api:
	$(BACKEND) uvicorn coffer.main:app --reload --port 8000

dev-web:
	$(FRONTEND) && npm run dev

test-backend:
	$(BACKEND) pytest $(ARGS)

lint:
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .
	$(BACKEND) pyright
	$(BACKEND) lint-imports

check-web:
	$(FRONTEND) && npx tsc --noEmit -p tsconfig.app.json && npx vitest run && npx vite build

# Same as the CI job: clean install from the lockfile, then the same steps as check-web.
check-web-clean:
	$(FRONTEND) && rm -rf node_modules && npm ci
	$(MAKE) check-web

check: lint test-backend check-web

openapi:
	$(BACKEND) python -m coffer.scripts.dump_openapi ../frontend/openapi.json
	$(FRONTEND) && npx openapi-typescript openapi.json -o src/api/schema.d.ts

seed:
	$(BACKEND) python -m coffer.scripts.seed_demo

mcp-market:
	@$(BACKEND) python -m coffer.market.mcp_server
