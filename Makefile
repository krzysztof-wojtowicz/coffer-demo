BACKEND = cd src/backend && uv run
FRONTEND = cd src/frontend

.PHONY: setup db-up db-down migrate dev-api dev-web test-backend lint check-web check openapi seed

setup:
	cd src/backend && uv sync
	cd src/frontend && npm install

db-up:
	docker compose up -d --wait db

db-down:
	docker compose down

migrate:
	$(BACKEND) alembic upgrade head

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

check: lint test-backend check-web

openapi:
	$(BACKEND) python -m coffer.scripts.dump_openapi ../frontend/openapi.json
	$(FRONTEND) && npx openapi-typescript openapi.json -o src/api/schema.d.ts

seed:
	$(BACKEND) python -m coffer.scripts.seed_demo
