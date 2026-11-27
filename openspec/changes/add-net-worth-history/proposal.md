## Why
The summary page shows net worth only for today. Users want to see how their cash on accounts changed month by month (F26).

## What Changes
- New endpoint `GET /api/budget/net-worth/history?months=12` (1–60, default 12) → `{points: [{month: "YYYY-MM", cash_balance: "0.00"}]}`.
- A pure series function in `coffer.analytics.net_worth`.
- A lightweight SVG line chart on the summary page, with an alternative table for screen readers and Polish labels.

## Capabilities
### Modified Capabilities
- `budget`: net worth gains a monthly cash history.

## Impact
- Backend: `src/backend/coffer/analytics/net_worth.py`, `src/backend/coffer/budget/{service,api,schemas}.py`
- Frontend: `src/frontend/src/features/budget/NetWorthChart.tsx` (new), `queries.ts`, `SummaryPage.tsx`
- Tests: `src/backend/tests/analytics/`, `src/backend/tests/budget/`, a frontend chart test

## Out of scope
Historical portfolio value (it is not stored) and forecasts.
