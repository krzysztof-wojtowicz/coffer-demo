## 1. Tester
- [ ] 1.1 Add Playwright (dev dependency, `playwright.config.ts`, `npm run e2e`, `make e2e`) with a backend on `COFFER_TEST_DB=coffer_test_e2e` and the LLM disabled
- [ ] 1.2 Flow: register → add a transaction → inline edit → delete via the dialog → summary matches to the grosz
- [ ] 1.3 Flow: CSV import from `data/fixtures/csv/` (preview → commit → re-import shows duplicates)
- [ ] 1.4 Flow: transaction list filters and sorting
- [ ] 1.5 Flow: add a manual holding; the net worth card shows the total
- [ ] 1.6 Flow: AI advisor with the model off shows the "bez AI" result; the rest of the app works
- [ ] 1.7 Flow: logout, then `/import` and `/profile` redirect to login
- [ ] 1.8 Optional CI job in `.github/workflows/ci.yml`

## 2. Verify
- [ ] 2.1 `make e2e` passes on a clean test database in under 3 minutes and leaves no data outside its own users
