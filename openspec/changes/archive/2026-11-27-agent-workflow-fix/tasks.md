# Tasks

Owners: all of this is markdown and moving files, so **docs-writer** does groups 1–3 and the orchestrator does group 2 itself. There is no implementer or tester work (no production code or tests change).

## 1. Agent definitions (docs-writer)

- [x] 1.1 `.claude/agents/tester.md`: add the rule to extend `tests/<module>/test_<module>.py` (frontend: the component's `*.test.tsx`) and never create parallel test files; add "one behaviour, one test, at the API level unless it is a pure function"; remove `FakeLLM`. Verify that the file stays under 30 lines and that `grep -n "FakeLLM\|tester.test" .claude/agents/tester.md` returns no instruction to create such files.
- [x] 1.2 `.claude/agents/implementer.md`: add a short "Refactor changes" block (delete first; extract a helper only for repetition in at least two places; public API unchanged unless the change says otherwise; English comments that say why). Verify that it stays under 35 lines.
- [x] 1.3 `.claude/agents/reviewer.md`: remove checklist item 4 (LLM privacy) and the `coffer.agent` rule; add "for refactor changes: behaviour unchanged, no test assertion edited without a reason, duplicate helpers and dead code flagged". Verify with a grep that the file has no `LLM` or `coffer.agent` mention.

## 2. Park feature changes (orchestrator)

- [x] 2.1 `git mv` the four changes `add-net-worth-history`, `add-e2e-playwright`, `add-transaction-server-filtering` and `improve-ui-kit-accessibility` from `openspec/changes/` to `openspec/parked/`, unchanged. Verify that `openspec list` no longer shows them and `ls openspec/parked` shows all four.

## 3. Workflow docs (docs-writer)

- [x] 3.1 `.claude/skills/orchestrate/SKILL.md`: add a "Refactor (behaviour unchanged)" row to the table in section 0, and a short section for it: implementers on disjoint modules (at most 3), existing tests as the safety net, then reviewer, then a report with `git diff --stat`. Verify that the skill stays under 90 lines and the existing paths are unchanged.
- [x] 3.2 `CLAUDE.md` Workflow and `docs/agents.md`: describe the refactor path, one test file per module, and `openspec/parked/` (move a change back to `openspec/changes/` to resume it). Verify that `CLAUDE.md` grows by at most 5 lines.

## 4. Verification

- [x] 4.1 Run `openspec validate --all --strict` (the parked changes are no longer listed, and the rest are valid). `make lint`, `make test-backend` and `make check-web` are unaffected because no code changed.

## Workflow follow-up

- Archive with `openspec-archive-change` (no specs to sync).
