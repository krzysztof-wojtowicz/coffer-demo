## ADDED Requirements

### Requirement: Net worth history
`GET /api/budget/net-worth/history?months=N` (1–60, default 12) SHALL return one point per month, oldest first, with the cash balance at the end of that month (today for the current month): the opening balance plus the sum of transactions up to that date. The series covers cash only. The summary page SHALL show it as a line chart with an accessible table alternative.

#### Scenario: Consistent with current net worth
- **WHEN** the user requests the history
- **THEN** the last point's `cash_balance` equals `cash_balance` from `GET /api/budget/net-worth`

#### Scenario: Out-of-range months
- **WHEN** `months` is below 1 or above 60
- **THEN** the system responds 422

#### Scenario: No opening balance
- **WHEN** no opening balance is set
- **THEN** balances are counted from zero
