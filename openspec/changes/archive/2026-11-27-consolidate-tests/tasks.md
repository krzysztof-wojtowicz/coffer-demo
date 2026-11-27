# Tasks

Owners: there are no production code changes, so no implementer. **tester** agents own the module groups on disjoint folders (at most 3 at once). Groups 2–4 depend on the fixtures in group 1. Record the test count and `wc -l` of `src/backend/tests` and the frontend test files before starting.

## 1. Shared fixtures and cross-cutting tests (tester A)

- [x] 1.1 Move the duplicated fixtures (users, logged-in clients, categories, the DB session) into `tests/conftest.py`, delete the per-folder copies, and delete `tests/integration/`. Verify that `make test-backend` passes.
- [x] 1.2 Create `tests/test_security.py`: a table over `app.routes` asserting 401 without a session (except the public ones), 404 for another user's resource in every module, and parametrized input bounds returning 422. Delete `accounts/test_auth_required.py` and every `test_vuln_*.py` whose cases it now covers. Verify that `make test-backend ARGS="tests/test_security.py"` passes, and that each deleted vuln case maps to a row in the table.
- [x] 1.3 Rename `test_migrations_e5.py` to `test_migrations.py` and fold in `accounts/test_tester_migration.py`. Verify that it passes.

## 2. Accounts and core (tester A, after group 1)

- [x] 2.1 Merge `accounts/` into `test_accounts.py` (from `test_auth_api`, `test_security`, `test_service`, `test_tester_auth`), deduplicating by design decision 1. Verify that every `accounts` spec scenario maps to a test and `make test-backend ARGS="tests/accounts"` passes.
- [x] 2.2 Merge `core/` into `test_core.py` (CORS, origin, body limit, db_url, clock), with the `test_tester_cors` duplicates removed. Verify that `make test-backend ARGS="tests/core"` passes.

## 3. Ledger modules (tester B)

- [x] 3.1 Merge `transactions/` into `test_transactions.py`, and `imports/` into `test_imports.py` plus `test_imports_parsing.py` (pure parser, dedup and categorizer). Verify that every `transactions` spec scenario maps to a test and both folders pass.
- [x] 3.2 Merge `budget/`, `cash/` and the non-agent cases from `contract_e5/` into `test_budget.py` and `test_cash.py`, then delete `contract_e5/`. Keep the hypothesis totals test (N04). Verify that every `budget` spec scenario maps to a test and the folders pass.
- [x] 3.3 Reduce `analytics/` to one test per pure function behaviour, parametrized, and delete the cases already covered through `test_budget.py`. Verify that `make test-backend ARGS="tests/analytics"` passes.

## 4. Portfolio and market (tester C)

- [x] 4.1 Merge `portfolio/`, `profile/`, `market/` and `scripts/` into one file per module. Keep the "market unavailable → manual or cost value" and the price-date (N07) cases. Verify that every `portfolio` spec scenario maps to a test and the folders pass.

## 5. Frontend (tester C, after group 4)

- [x] 5.1 Merge each `*.tester.test.ts(x)` into the `*.test.ts(x)` next to it (create one where none exists) and delete the `.tester` files. Remove duplicate assertions. Verify that `find src/frontend/src -name '*.tester.test.*'` is empty and `make check-web` passes.

## 6. Verification

- [x] 6.1 Run `make test-backend`, `make check-web`, `make lint` and `openspec validate consolidate-tests --strict`. All must pass. Report the before/after test count and lines, and the scenario → test map in the PR description.

## Workflow follow-up

- Review with the `reviewer` agent (every scenario covered; no regression test lost).
- Archive with `openspec-archive-change` (no specs to sync).
