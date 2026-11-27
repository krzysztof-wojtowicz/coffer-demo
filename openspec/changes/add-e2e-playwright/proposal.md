## Why
The main user flows are tested only in unit and API tests. Browser tests against the real backend would catch integration regressions in the UI.

## What Changes
- Playwright end-to-end tests in `src/frontend/e2e/` and a `make e2e` target.
- They run against the real backend with a test database and `COFFER_LLM_PROVIDER=none` (or `FakeLLM`), with no external network (no yfinance, no LLM).

## Capabilities
### New Capabilities
- `e2e-testing`: browser-level coverage of the key flows.

## Impact
- `src/frontend/e2e/**`, `src/frontend/playwright.config.ts`, `src/frontend/package.json` (script and dev dependency), `Makefile` (`e2e` target)
- Best done after `add-transaction-server-filtering`, because it changes the transaction list UI.

## Out of scope
Visual (screenshot) tests, production tests, multiple browsers.
