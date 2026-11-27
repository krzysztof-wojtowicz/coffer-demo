# Proposal

## Why

Tests outnumber code: about 12,000 lines of backend tests against about 11,500 lines of code. Once the agent is removed, about 440 non-AI tests remain, spread over 4–9 files per module, and many test the same behaviour twice. That happened because the tester agent wrote parallel suites (`test_tester_*.py`, `contract_e5/`, `test_vuln_*.py`, `*.tester.test.tsx`) next to the originals. Duplicated tests slow every refactor and hide which test actually protects a requirement. With `agent-workflow-fix` stopping new duplicates, this change removes the existing ones.

## What Changes

- Backend: one test file per module, `tests/<module>/test_<module>.py`, with a pure `tests/<module>/test_<unit>.py` only where pure-function tests are large (`analytics`, `imports` parser and categorizer). Merge in and then delete the `test_tester_*`, `test_vuln_*`, `test_n05`, `test_update`, `test_hints` and similar files and the `contract_e5/` folder.
- One cross-cutting `tests/test_security.py`: every non-public endpoint requires a session (a parametrized table over the routes), another user's resource returns 404, and input bounds (NUL bytes, huge numbers, long strings) return 422 and not 500. This replaces the per-module copies of these checks.
- Each spec scenario keeps at least one test. Tests that assert the same behaviour as another test, or only check framework behaviour (Pydantic or FastAPI doing what they always do), are deleted.
- Shared fixtures go into the top-level `tests/conftest.py` (users, logged-in clients, categories); per-folder conftests that duplicate them go. The empty `tests/integration/` is deleted.
- Frontend: merge each `*.tester.test.ts(x)` into its `*.test.ts(x)` and delete it.
- Target: about half of the remaining non-AI test lines and test count, with no spec scenario left untested.

Out of scope:
- Production code changes (`simplify-backend`), new tests for untested behaviour, and E2E tests (the parked `add-e2e-playwright`).
- Changing the test tooling (pytest, hypothesis, vitest) or `make` targets.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none: tests only (`skip_specs: true`) -->

## Impact

- `src/backend/tests/**` (restructured), and `src/frontend/src/**/*.tester.test.ts(x)` merged into the files next to them.
- Depends on `remove-ai-agent` (agent tests already gone) and is best run after `simplify-backend`, so the tests are merged once against the final code.
