# Spec Delta: budget

## REMOVED Requirements

### Requirement: Category limits (F13, F14)
**Reason**: The feature is unused and clutters the Summary page. It is dropped to keep the budget module small.
**Migration**: There is no replacement. `/api/budget/limits` endpoints and the `limits` field of `GET /api/budget/{month}/insights` are removed, and migration 0012 drops the `budget_limits` table. The downgrade recreates an empty table.
