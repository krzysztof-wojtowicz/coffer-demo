# Glossary

One term, one meaning. Polish UI names are in parentheses.

| Term | Meaning |
|---|---|
| **User** | One person with an account who manages their own finances. |
| **Budget** | A user's income and expenses in one calendar month. |
| **Transaction** | One money flow on the user's account: date, amount (positive = income, negative = expense), description, category. |
| **Income / Expense** | A transaction that increases / decreases the user's funds. |
| **Category** | A label grouping transactions by purpose (food, transport, housing…). Every transaction has exactly one. Categories are global; "Inne" is the default; "Przelewy własne" (own transfers) and "Inwestycje" (investments) are outside the budget. |
| **Surplus** (nadwyżka) | Income minus expenses of the month in in-budget categories, when positive. The month tiles (income, expenses, balance) count all transactions and are not the surplus. The sum of monthly balances equals the sum of transactions. |
| **Savings goal** | An amount the user wants to collect by a date (not implemented). |
| **Asset / asset class** | Something the user owns, in one of the classes: `stock`, `etf`, `bond`, `cash`, `crypto`, `commodity`, `real_estate` (one list shared by portfolio and profile). |
| **Holding** (pozycja) | A specific asset in the portfolio with quantity, purchase price and date. |
| **Portfolio** | All of a user's holdings. |
| **Portfolio value** | Sum of all holdings at the last known price, in the base currency. |
| **Base currency** | The currency of all totals (PLN). |
| **Target allocation** | The share of each asset class suggested by the user's profile (horizon, risk, preferred classes); an illustrative table in `analytics.allocation`, not advice. |
| **Gap from target** | Current share minus target share of a class, in percentage points; the total gap is half the sum of absolute gaps, i.e. the part of the portfolio that would have to move. |
| **Investment profile** | The user's declared horizon, risk tolerance (low / medium / high) and preferred asset classes. |
| **Opportunity** | An asset matching the investment profile that the user doesn't hold yet. |
| **Monthly analysis** | The summaries for one month: expenses by category, income, surplus, change versus the previous month. |
| **Net worth** (majątek) | Cash on accounts plus portfolio value. Cash = opening balance (amount and date set by the user) plus transactions since that date up to today, or from zero without an opening balance. `portfolio_complete` says whether every holding has a current price. |
| **Forecast** | An estimate of the month-end balance from transactions so far (F18, not done). |
| **Price job** | Refreshing quotes and FX rates into `market_quotes`: `make prices`, or an optional in-API thread (`COFFER_PRICE_REFRESH_MINUTES`, off by default). |
