## MODIFIED Requirements

### Requirement: Listing transactions
A user SHALL be able to list their own transactions at `GET /api/transactions` with server-side filters (`date_from`, `date_to`, `type=income|expense`, `category_id`, `source=manual|import`, text `q`), sorting (`sort=date|amount`, `order=asc|desc`, stable with `id` as the second key) and paging (`limit` default 50, max 200, and `offset`). The response SHALL be `{items, total}`. The `month=YYYY-MM` parameter SHALL keep working.

#### Scenario: Month filter
- **WHEN** the user lists transactions for a month
- **THEN** only that user's transactions dated in that month are returned

#### Scenario: Date range and filters
- **WHEN** the user filters by a date range, type, category, source and text
- **THEN** `items` contains only matching transactions of that user and `total` counts all matches

#### Scenario: Reversed date range
- **WHEN** `date_from` is after `date_to`
- **THEN** the system responds 422 "Nieprawidłowy zakres dat"

#### Scenario: Offset past the end
- **WHEN** `offset` is greater than or equal to `total`
- **THEN** `items` is empty and `total` is unchanged

#### Scenario: Isolation
- **WHEN** another user has matching transactions
- **THEN** they appear in neither `items` nor `total`
