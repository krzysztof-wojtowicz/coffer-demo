# Design

## Context

Per-module backend test files after `remove-ai-agent`: accounts 7, imports 6, transactions 5, budget 4, portfolio 3, core 6, plus `contract_e5/` (two files with non-agent cases), `test_migrations_e5.py` and `test_health.py`. Fixtures are defined in `tests/conftest.py` and again in the `accounts/`, `market/` and `contract_e5/` conftests.

## Goals / Non-Goals

**Goals:**
- Anyone can find "the test for requirement X" in one obvious file.
- Fewer tests and lines, and every `#### Scenario` in `openspec/specs/` still covered.

**Non-Goals:**
- Raising coverage or rewriting tests that are fine; moving a good test as it is beats rewriting it.

## Decisions

1. **What to keep.** Keep a test if it is the only one covering a spec scenario, a hard rule (Decimal and rounding, user isolation, migrations with one head), or a bug that really happened (its regression test). Delete a test if another test asserts the same outcome through the same path, or if it only checks library behaviour. When two tests overlap, keep the one at the API level and delete the service-level copy, unless the logic is a pure function.

2. **Parametrize instead of copying.** Families like "field X rejects NUL / too long / negative" become one parametrized test per module. The session-required checks become one table in `test_security.py` built from `app.routes`, so new endpoints are covered automatically without new tests.

3. **Scenario map as the safety net.** Before deleting, the tester lists each spec scenario with the test that covers it, in the PR description only (not committed). Nothing is deleted that would leave a scenario unmapped.

4. **Migrations.** `test_migrations_e5.py` becomes `tests/test_migrations.py`: upgrade to head, downgrade to base, one head, CASCADE from `users`. The stage-specific checks are folded in.

## Risks / Trade-offs

- [A deleted test was the only guard of an edge case that isn't in the spec] → Decision 1 keeps regression tests. The reviewer compares the before/after test names for each module.
- [Large merged files become hard to read] → Group tests in classes or sections by spec requirement, with the requirement name as a comment header.
