# Vision

## Problem
Managing day-to-day and long-term finances is hard and scattered across many sources. Coffer brings them into one system that helps with analysis, forecasts, investment plans and asset purchases.

## Users
A person managing their own budget, with no expert financial knowledge, who wants to understand it. (Family and business budgets were considered and left out; see N2 below.)

## Scenarios
- **Monthly budget review:** what did I spend on and how much, can I save, where and how should I invest the surplus?
- **Buying assets:** what do I already own, what fits my portfolio, what might interest me, and what can I find online about a company?
- **Saving:** where can I stop spending, and how do I start saving month by month?

## Role of the AI assistant
Finding opportunities, analysing the portfolio in context, and showing suggestions about asset purchases. **Currently removed:** it will be rebuilt for local LLMs after the refactor (F31–F38 and N03 are unimplemented; see the [roadmap](roadmap.md)).

## Scope
In: UI, database, an engine that analyses the portfolio and purchases (the AI assistant is planned, see above).
Out: payments (W1), bank API integration (W2), autonomous purchases (W3), shared multi-user budgets (W4).

## Clarified ambiguities
| # | Vision phrase | Problem | Decision |
|---|---|---|---|
| N1 | "multi-source finance management" | Where does data come from if bank APIs are out of scope? | The **user** enters data manually or imports a bank-statement CSV. |
| N2 | "family / small business / company budget" | Businesses need VAT, accounting and permissions. | Version 1 handles one person's **personal budget**. |
| N3 | "where and how to invest", "what fits my portfolio" | Sounds like regulated investment advice. | The system shows informational **suggestions** with reasoning and a disclaimer, not recommendations. |
| N4 | "forecasts" | Forecasts of what, over what horizon? | Budget and asset balance at the end of the current and next month (F18, not done). |
| N5 | "assets / real estate" | Which asset classes? | Cash, deposits, stocks, ETFs, bonds, crypto, real estate. |
| N6 | "opportunities" | No criterion for an opportunity. | An **opportunity** is an asset matching the user's **investment profile** that they don't hold yet. |

## Assumptions
- **A1.** Users can get their transaction history (e.g. a bank CSV) and want to load it.
- **A2.** Users know what their portfolio contains and enter it themselves.
- **A3.** Users are online when refreshing market prices.
- **A4.** One base currency per user (PLN by default); other currencies convert at the daily rate (not implemented yet: only PLN is accepted).
- **A5.** The system never executes financial operations; it only analyses and informs.
- **A6.** Users accept that the system stores their financial data.

## Requirements
Functional (F01–F38) and non-functional (N01–N09) requirements are specified as capabilities in [`openspec/specs/`](../openspec/specs): `accounts`, `transactions`, `budget`, `portfolio`. The AI requirements (F31–F38, N03) are currently unimplemented. N06 (Polish UI) applies everywhere. Priorities follow MoSCoW (M/S/C/W); everything M and S is implemented, and the open C items are in the [roadmap](roadmap.md).
