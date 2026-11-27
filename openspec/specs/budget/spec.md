# budget Specification

## Purpose
Monthly budget analysis, month-over-month comparisons, and net worth (cash plus portfolio). Covers F10–F12, F15, F17, F26 and N04 (former UC-11). All totals are computed in `coffer.analytics`.

## Requirements

### Requirement: Monthly summary (F10, F11)
`GET /api/budget/{month}` SHALL return, for one calendar month, total income, total expenses, the balance, the surplus, and expenses per category. Income, expenses and balance count every transaction of the month. The surplus counts only in-budget categories (it excludes "Przelewy własne" and "Inwestycje") and is never negative.

#### Scenario: Month with transactions
- **WHEN** the user opens a month with transactions
- **THEN** the response contains income, expenses, balance, surplus and per-category expenses as decimal strings

#### Scenario: Empty month
- **WHEN** the month has no transactions
- **THEN** all totals are "0.00" and the UI says the month has no transactions

#### Scenario: Deficit
- **WHEN** in-budget expenses exceed income
- **THEN** the surplus is "0.00" and the UI shows the deficit

#### Scenario: Invalid month
- **WHEN** the month is malformed or outside 1900–2099
- **THEN** the system responds 422, never 500

### Requirement: Exact totals (N04)
All totals SHALL equal the sum of source transactions to the grosz. Money SHALL be Decimal, rounded with ROUND_HALF_UP, and sent as strings.

#### Scenario: Sum consistency
- **WHEN** totals are computed for any set of transactions (property-based test)
- **THEN** the sum of monthly balances equals the sum of all transactions

### Requirement: Month comparison and top growth (F12, F15)
`GET /api/budget/{month}/insights` SHALL return per-category expense changes versus the previous month in PLN and percent, and the 3 categories whose spending grew most versus the average of the previous 3 months.

#### Scenario: Comparison
- **WHEN** both months have expenses in a category
- **THEN** the comparison shows the current amount, the previous amount, the change and the change percent

#### Scenario: Previous month was zero
- **WHEN** the previous month had no expenses in a category
- **THEN** `change_pct` is null

#### Scenario: Fewer than 3 prior months
- **WHEN** fewer than 3 earlier months have data
- **THEN** the average uses the months that are available

### Requirement: Opening balance
A user SHALL be able to set, read and delete an opening cash balance as an amount with an `as_of` date (`/api/cash/opening-balance`).

#### Scenario: Set opening balance
- **WHEN** the user saves an amount and a date
- **THEN** cash on accounts is computed from that balance plus the transactions dated after it

### Requirement: Net worth (F26)
`GET /api/budget/net-worth` SHALL return the cash balance (opening balance plus the sum of transactions up to today, counted from zero when no opening balance is set), the portfolio value, the net worth (cash plus portfolio), a `portfolio_complete` flag that is false when any holding lacks a current price, `opening_balance_set`, and `as_of`.

#### Scenario: Incomplete valuation
- **WHEN** at least one holding has no current price
- **THEN** `portfolio_complete` is false and the UI marks the value as incomplete

### Requirement: Works without AI (N08)
The budget features SHALL NOT depend on the AI agent.

#### Scenario: LLM unavailable
- **WHEN** no LLM provider is configured or reachable
- **THEN** every budget endpoint responds normally
