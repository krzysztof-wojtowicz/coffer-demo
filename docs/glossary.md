# Glossary

One term, one meaning. Polish UI names are in parentheses.

| Term | Meaning |
|---|---|
| **User** | One person with an account who manages their own finances. |
| **Budget** | A user's income and expenses in one calendar month. |
| **Transaction** | One money flow on the user's account: date, amount (positive = income, negative = expense), description, category. |
| **Income / Expense** | A transaction that increases / decreases the user's funds. |
| **Category** | A label grouping transactions by purpose (food, transport, housing…). Every transaction has exactly one. Categories are global; "Inne" is the default; "Przelewy własne" (own transfers) and "Inwestycje" (investments) are outside the budget. |
| **Surplus** (nadwyżka) | Income minus expenses of the month in in-budget categories, when positive. The month tiles (income, expenses, balance) count all transactions and are not the surplus. *Investment ideas* uses the surplus as the default amount. The sum of monthly balances equals the sum of transactions. |
| **Spending limit / category limit** | A fixed monthly amount the user sets for one in-budget category (`budget_limits`). Usage is computed by `analytics`; *Budget plan* can propose limits to apply. |
| **Savings goal** | An amount the user wants to collect by a date (only as a parameter of *Budget plan*; not stored). |
| **Asset / asset class** | Something the user owns, in one of the classes: cash, deposit, stocks, ETF, bonds, crypto, real estate (portfolio code also has `commodity`). |
| **Holding** (pozycja) | A specific asset in the portfolio with quantity, purchase price and date. |
| **Portfolio** | All of a user's holdings. |
| **Portfolio value** | Sum of all holdings at the last known price, in the base currency. |
| **Base currency** | The currency of all totals (PLN). |
| **Investment profile** | The user's declared horizon, risk tolerance (low / medium / high) and preferred asset classes. |
| **Suggestion** | An AI-agent output with reasoning based on the user's data and a disclaimer that it is not advice. The user always decides. |
| **Opportunity** | An asset matching the investment profile that the user doesn't hold yet. |
| **Monthly analysis** | The summaries for one month: expenses by category, income, surplus, change versus the previous month. |
| **Net worth** (majątek) | Cash on accounts plus portfolio value. Cash = opening balance (amount and date set by the user) plus transactions since that date up to today, or from zero without an opening balance. `portfolio_complete` says whether every holding has a current price. |
| **Forecast** | An estimate of the month-end balance from transactions so far (F18, not done). |
| **AI agent** | The part of the system that uses an LLM to run actions on request. |
| **Agent action** | One AI function from the catalog of six (`portfolio_review`, `investment_ideas`, `savings_analysis`, `purchase_impact`, `budget_plan`, `company_research`) run through one endpoint. It has parameters, allowed tools, a versioned prompt and a rule-based result. |
| **Tool catalog** | The registry of 22 tools (user data, calculations, market data) used during actions; each action has its own allow-list. |
| **Run / trace** (przebieg, ślad) | The record of one action run (`agent_runs`): params, steps, tools called, tokens, time and status. Visible in history. |
| **Trace step** | One element of a run: tool call, model call, validation, fallback, limit or error. |
| **Rule-based result / fallback** | An action report built without the model from computed facts, shown when AI is unavailable, the limit is reached, time ran out or the answer was invalid. Labelled "bez AI" (`source: rules`). |
| **Price job** | Refreshing quotes and FX rates into `market_quotes`: `make prices`, or an optional in-API thread (`COFFER_PRICE_REFRESH_HOURS`, off by default). |
