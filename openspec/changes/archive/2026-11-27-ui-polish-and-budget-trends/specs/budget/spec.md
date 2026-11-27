# Spec Delta

## MODIFIED Requirements

### Requirement: Opening balance
A user SHALL be able to set, read and delete an opening cash balance as an amount with an `as_of` date (`/api/cash/opening-balance`). The amount is the balance at the start of `as_of`, before any transaction dated that day.

#### Scenario: Set opening balance
- **WHEN** the user saves an amount and a date
- **THEN** cash on accounts is computed from that balance plus the transactions dated on or after it

#### Scenario: Transactions on the opening-balance day
- **WHEN** the opening balance is 5000.00 as of 2026-09-01 and transactions of +8500.00 and -264.15 are dated 2026-09-01
- **THEN** both transactions count toward cash, and the cash balance before later transactions is 13235.85

#### Scenario: Transactions before the opening-balance day
- **WHEN** a transaction is dated before `as_of`
- **THEN** it does not count toward cash

#### Scenario: Hint in settings
- **WHEN** the user opens the opening-balance form
- **THEN** the hint says the amount is the balance at the start of the chosen day and that transactions from that day on are added

### Requirement: Net worth (F26)
`GET /api/budget/net-worth` SHALL return the cash balance (opening balance plus the sum of transactions dated from `as_of` through today, counted from zero over all transactions up to today when no opening balance is set), the portfolio value, the net worth (cash plus portfolio), a `portfolio_complete` flag that is false when any holding lacks a current price, `opening_balance_set`, and `as_of`.

#### Scenario: Incomplete valuation
- **WHEN** at least one holding has no current price
- **THEN** `portfolio_complete` is false and the UI marks the value as incomplete

#### Scenario: Months add up to cash
- **WHEN** an opening balance is set and every month from `as_of` to today is fully dated on or after `as_of`
- **THEN** the cash balance equals the opening balance plus the sum of those months' balances

#### Scenario: Future transactions
- **WHEN** a transaction is dated after today
- **THEN** it does not count toward cash

## ADDED Requirements

### Requirement: Spending trend window (F10, F12)
`GET /api/budget/{month}/trend?months=N` SHALL return the N calendar months ending with `month` (N is 3, 6 or 12, default 6), oldest first. Each month SHALL carry income, expenses, balance, surplus and savings rate. The savings rate is surplus divided by in-budget income (income outside "Przelewy własne" and "Inwestycje"), as a percent with one decimal, and null when in-budget income is zero.

#### Scenario: Default window
- **WHEN** the user requests the trend for 2026-11 without `months`
- **THEN** the response lists 2026-06 through 2026-11, oldest first, with totals as decimal strings

#### Scenario: Window crosses a year
- **WHEN** the user requests 3 months ending 2026-01
- **THEN** the months are 2025-11, 2025-12 and 2026-01

#### Scenario: Savings rate
- **WHEN** a month has income 8500.00 and in-budget expenses 3712.16
- **THEN** its surplus is "4787.84" and its savings rate is "56.3"

#### Scenario: Transfers between own accounts
- **WHEN** the same month also has an incoming "Przelewy własne" transaction of +1000.00 and an outgoing one of -1000.00
- **THEN** income is "9500.00", but the surplus stays "4787.84" and the savings rate stays "56.3"

#### Scenario: Investment sale
- **WHEN** a month has a positive "Inwestycje" transaction (e.g. an ETF sold to cash)
- **THEN** it counts in income but not in the savings rate

#### Scenario: No in-budget income
- **WHEN** a month has no income outside "Przelewy własne" and "Inwestycje"
- **THEN** its savings rate is null

#### Scenario: Unsupported window or month
- **WHEN** `months` is not 3, 6 or 12, or `month` is malformed or outside 1900–2099
- **THEN** the system responds 422, never 500

#### Scenario: Another user's data
- **WHEN** two users have transactions in the same months
- **THEN** each user's trend counts only their own transactions

### Requirement: Comparison with the window average (F12, F15)
The trend SHALL include the average income, expenses and surplus of the months before `month` in the window that have at least one transaction, the average savings rate (average surplus over average in-budget income), and `month`'s change against each: in PLN and percent for amounts, in percentage points for the savings rate. With no such month, averages and changes SHALL be null.

#### Scenario: Change against the average
- **WHEN** the earlier months in the window with transactions had expenses 3000.00 and 5000.00 and `month` has expenses 4400.00
- **THEN** the average expenses are "4000.00", the change is "400.00" and the change percent is "10.0"

#### Scenario: Empty months are not averaged
- **WHEN** some earlier months in the window have no transactions
- **THEN** they are left out of the averages

#### Scenario: No earlier data
- **WHEN** no earlier month in the window has a transaction
- **THEN** the averages and changes are null and the UI shows "brak danych"

### Requirement: Category spending over time (F12, F15)
The trend SHALL list every in-budget category with expenses in any month of the window, with its expenses per month (zero where none), its average over the earlier months used for the window average, and `month`'s change against that average in PLN and percent (percent null when the average is zero). Categories SHALL be ordered by `month`'s expenses, then window total, both descending, then by name.

#### Scenario: Category amounts per month
- **WHEN** "Jedzenie" had 926.09 in 2026-09, nothing in 2026-10 and 1895.24 in 2026-11
- **THEN** its monthly amounts for a 3-month window ending 2026-11 are "926.09", "0.00" and "1895.24"

#### Scenario: Out-of-budget categories
- **WHEN** the window has expenses in "Inwestycje" or "Przelewy własne"
- **THEN** those categories are not listed

#### Scenario: New category
- **WHEN** a category has expenses only in `month`
- **THEN** its average is "0.00", its change equals its expenses, and its change percent is null

#### Scenario: Summary page
- **WHEN** the user opens a month on the summary page
- **THEN** the page shows a window selector (3, 6 or 12 months), stat tiles with each value's change against the window average, an income and expenses column chart over the window, and a category list where each row shows a sparkline, this month's amount, the average and the change

## REMOVED Requirements

### Requirement: Month comparison and top growth (F12, F15)
**Reason**: Comparing only with the previous month hides trends; the category trend over a 3–12 month window covers both the comparison (F12) and growth against an average (F15).
**Migration**: Use `GET /api/budget/{month}/trend`; the previous month's amounts are in the returned months, and growth is the category change against the window average. `GET /api/budget/{month}/insights` is removed.
