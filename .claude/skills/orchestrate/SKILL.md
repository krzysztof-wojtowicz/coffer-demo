---
name: orchestrate
description: Run a piece of work in the Coffer repo with the agent team (implementer, tester, reviewer, docs-writer, explorer) on top of OpenSpec. Use when the user asks to build, fix or ship a feature or change ("implement add-net-worth-history", "build X", "do the next change", "review and ship"), or asks for a team of agents.
---

# Orchestrate

You are the orchestrator in the main session. You plan, delegate, integrate and report; agents write the code. Keep your own context small: don't read the code agents wrote when tests and lint pass.

## 0. Pick the workflow
| Request | Workflow |
|---|---|
| Something new or a behaviour change | full loop (1–6) |
| Refactor (behaviour unchanged) | see "Refactor path" below |
| Bug fix with a clear cause | skip 1 if no spec changes; implementer + tester for a regression test; review |
| Docs only | `docs-writer` alone |
| "Where/how is X" | `explorer` alone |
| Review a branch or PR | `reviewer` alone (`security-review` too when auth or data changed) |
| One-line change | do it yourself; no agents |

## Refactor path (behaviour unchanged)
No new spec delta (`skip_specs`). Run implementers on disjoint modules (at most 3); the existing tests are the safety net, so no tester unless tests are the subject of the change. Then `make check`, then `reviewer`, who checks that behaviour is unchanged. Report with `git diff --stat` and the line count before/after.

## 1. Spec (OpenSpec)
- An existing change: `openspec list`, then read `openspec/changes/<name>/{proposal,tasks}.md` and its delta specs.
- A new one: use the `openspec-propose` skill (or `openspec-explore` first if the idea is fuzzy). `tasks.md` must group tasks by owner (implementer / tester) with **disjoint files**.
- Run `openspec validate <name> --strict`. Show the user the proposal and get approval before building.

## 2. Build (parallel, in the background)
Start the implementer and the tester **at the same time** in one message. The prompts stay short because the context lives in the files:

```
Change: openspec/changes/<name>
Your files: <paths from tasks.md>
Test DB: coffer_test_<module>
```

- A change touching backend and frontend gets two implementers, one per side, with disjoint files.
- At most 3 agents at once.
- The tester works from the spec, never from the implementation; this guards against tests that just mirror the code.
- Shared files (`main.py`, `core/config.py`, `i18n/pl.ts`, `App.tsx`, `.env.example`) get exactly one owner per change.

## 3. Integrate
1. Run the module tests: `COFFER_TEST_DB=coffer_test_<module> make test-backend ARGS="tests/<module>" 2>&1 | tail -30` and/or `make check-web`.
2. On failure, decide by the **spec**:
   - the code is wrong → `SendMessage` to the implementer with the test names and a short error (not the whole log);
   - the test contradicts the spec → `SendMessage` to the tester;
   - the spec is unclear → fix the delta spec (`openspec-update-change`), then tell both agents.
3. At most 2 fix rounds, then stop and ask the user.
4. Run `make openapi` once if the API changed (agents don't, to avoid conflicts on generated files), then `make check`, which must pass.

## 4. Review
Run `reviewer` on the working-tree diff with the change name. Send blockers and majors back to the implementer (continue the same agent with `SendMessage`); list minors and nits for the user. For auth, sessions, personal data or LLM prompts, also ask the reviewer to focus on security and privacy.

## 5. Docs
If behaviour or setup changed beyond the specs, run `docs-writer` (README, `docs/architecture.md`, `docs/development.md`, `docs/roadmap.md`).

## 6. Finish
- Archive the change with the `openspec-archive-change` skill (it merges the deltas into `openspec/specs/`).
- Report to the user in ≤ 10 lines: what shipped, test results, decisions, open issues.
- Commit only when the user asks: one commit per change, message `<change-name>: <summary>`.

## Token economy
- Continue an existing agent with `SendMessage` instead of spawning a fresh one; it keeps its context.
- Agent reports are ≤ 15 lines and contain no code. Trim logs with `| tail -30`.
- Models are set by the agent definitions (opus reviewer, sonnet implementer/tester/docs-writer, haiku explorer); override only when the user asks.
- Use `explorer` for lookups that would otherwise pull many files into your context.
