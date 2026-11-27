## Why
The transaction list is limited to one month and filters and sorts in the browser. Users with long histories need date ranges, server-side filtering and paging (F06, former UC-03).

## What Changes
- `GET /api/transactions` accepts `date_from`, `date_to`, `type=income|expense`, `category_id`, `source=manual|import`, `q`, `sort=date|amount`, `order=asc|desc`, `limit` (default 50, max 200) and `offset`. `month` stays for compatibility.
- **BREAKING**: the response changes from a list to `{items: TransactionOut[], total: int}`. The frontend and `make openapi` change in the same change.
- UI: filters are sent to the API, a date range replaces the month picker, and the list gets "Pokaż więcej" or pagination.

## Capabilities
### Modified Capabilities
- `transactions`: listing gains server-side filters, sorting and paging.

## Impact
- Backend: `src/backend/coffer/transactions/{api,service,schemas}.py`
- Frontend: `src/frontend/src/features/transactions/{TransactionsPage.tsx,list.ts,queries.ts}`, regenerated `openapi.json` / `schema.d.ts`
- Tests: `src/backend/tests/transactions/`, `src/frontend/src/features/transactions/list.test.ts`

## Out of scope
CSV export (F09) and saved filters.
