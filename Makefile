BACKEND = cd src/backend && uv run
FRONTEND = cd src/frontend

.PHONY: setup db-up db-down migrate dev-api dev-web test-backend lint check-web check-web-clean check openapi seed prices openspec-skills

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

# Clean install from the lockfile, then the same steps as check-web.
check-web-clean:
	$(FRONTEND) && rm -rf node_modules && npm ci
	$(MAKE) check-web

check: lint test-backend check-web

openapi:
	$(BACKEND) python -m coffer.scripts.dump_openapi ../frontend/openapi.json
	$(FRONTEND) && npx openapi-typescript openapi.json -o src/api/schema.d.ts

seed:
	$(BACKEND) python -m coffer.scripts.seed_demo

prices:
	$(BACKEND) python -m coffer.scripts.refresh_prices

# Refresh OpenSpec skills for Claude Code as real files in .claude/skills (openspec 2.x writes
# symlinks into .agents/, which we don't keep).
openspec-skills:
	openspec update --force .
	for d in .claude/skills/openspec-*; do [ -L "$$d" ] && cp -RL "$$d" "$$d.tmp" && rm "$$d" && mv "$$d.tmp" "$$d"; done; true
	rm -rf .agents
