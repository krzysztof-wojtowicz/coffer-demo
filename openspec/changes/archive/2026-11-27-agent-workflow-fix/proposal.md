# Proposal

## Why

The agent workflow in `.claude/` is built for adding features, and the way it runs leaves duplicated tests behind. The tester writes "independent" tests in new files instead of extending the module's existing ones, which is how `test_tester_*.py`, `contract_e5/`, `e5/` and the `test_vuln_*.py` files ended up next to the original suites (backend and `*.tester.test.tsx` in the frontend). The next phase is refactoring (removing and simplifying code without changing behaviour), and the workflow has no path for that. This change has to land first; otherwise `consolidate-tests` gets undone by the next change.

## What Changes

- `orchestrate` skill: add a **Refactor** path for changes that keep behaviour (no new spec). It runs implementer agents on disjoint modules, uses the existing tests as the safety net with no tester agent, and has the reviewer check that behaviour is unchanged. It reports `git diff --stat` (lines removed) at the end. The other paths stay as they are.
- `tester` agent: add tests to the module's existing test file (`tests/<module>/test_<module>.py`; next to the component for the frontend). Never create parallel files (`test_tester_*`, `*.tester.test.tsx`, `test_vuln_*`, `contract_*`, stage folders). Test each behaviour once, at the API level unless the logic is a pure function. Keep the "test from the spec, not the implementation" rule. Drop the `FakeLLM` mention.
- `implementer` agent: add refactor rules. Delete before abstracting. Extract a shared helper only when it removes repetition in at least two places. Keep the public API unchanged unless the change says otherwise. Write comments in English that explain *why*, not *what*.
- `reviewer` agent: remove the LLM privacy item (N03) and the `coffer.agent` import rule, which go away with `remove-ai-agent`. Add a simplicity check against duplicate helpers and dead code, and for refactor changes a "behaviour unchanged" check (no edited test assertions without a reason).
- Park the four feature changes (`add-net-worth-history`, `add-e2e-playwright`, `add-transaction-server-filtering`, `improve-ui-kit-accessibility`) by moving them unchanged to `openspec/parked/`, which `openspec list` does not read.
- `CLAUDE.md` (Workflow section) and `docs/agents.md`: describe the refactor path, the one-test-file-per-module rule and `openspec/parked/`.

Out of scope:
- Merging or deleting existing tests (`consolidate-tests`) and any production code change.
- The generated `openspec-*` skills (refreshed only with `make openspec-skills`), `ponytail` and `frontend-design`.
- Model choices per agent and `.claude/settings.json` permissions.

## Capabilities

### New Capabilities
<!-- none: tooling only -->

### Modified Capabilities
<!-- none: no spec-level behaviour changes (`skip_specs: true`) -->

## Impact

- Files: `.claude/skills/orchestrate/SKILL.md`, `.claude/agents/{tester,implementer,reviewer}.md`, `CLAUDE.md`, `docs/agents.md`.
- Moved: `openspec/changes/{add-net-worth-history,add-e2e-playwright,add-transaction-server-filtering,improve-ui-kit-accessibility}/` → `openspec/parked/`.
- Order: apply this change before `remove-ai-agent`, `simplify-backend` and `consolidate-tests`.
