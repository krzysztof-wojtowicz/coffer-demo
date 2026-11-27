## 1. Implementer
- [ ] 1.1 Add a pure monthly cash-balance series function to `analytics/net_worth.py`
- [ ] 1.2 Add the endpoint and schema in `budget/{service,api,schemas}.py`; register the route before `/{month}`
- [ ] 1.3 Add `NetWorthChart.tsx` (SVG line chart plus screen-reader table, no heavy chart dependency) and show it on `SummaryPage.tsx`

## 2. Tester
- [ ] 2.1 Hypothesis test: each point equals opening balance + sum of transactions up to the end of that month
- [ ] 2.2 The last point equals `cash_balance` from `GET /api/budget/net-worth`
- [ ] 2.3 `months` bounds (0 and 61 → 422) and user isolation
- [ ] 2.4 Frontend test for the chart and its table

## 3. Verify
- [ ] 3.1 `make lint`, `COFFER_TEST_DB=coffer_test_budget make test-backend ARGS="tests/budget tests/analytics"`, `make check-web`, `make openapi`
