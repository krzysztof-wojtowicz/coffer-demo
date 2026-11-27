# Proposal: wallet-grouped-positions

## Why

Every purchase is stored as its own holding, so buying the same stock, ETF or crypto several times fills the Wallet table with repeated rows. The user can't see the total quantity, average purchase price or total gain per instrument. The list also has no filters or sorting, and the "Dodaj pozycję" button sits below the table, unlike the Transactions page.

## What Changes

- **Grouped positions:** holdings with the same ticker (trimmed, case-insensitive) form one position, whatever their currency. Each holding without a ticker is its own position. Every position, even one with a single holding, has a header row with totals in PLN: quantity, cost, value, gain (PLN and %), share of the portfolio and average purchase price per unit. The header shows the name of the newest holding.
- **Expandable lots:** positions start collapsed. Clicking the header shows the position's holdings ("lots"), ordered by purchase date. Each lot shows its purchase date, quantity, purchase price, cost, value and gain (amount and %) in the lot's own currency, with "Edytuj" and "Usuń" buttons. The header row has no edit or delete actions.
- **API:** `GET /api/portfolio/summary` gains a `positions` list. Each position has its PLN totals and its lots, and each lot has its amounts in its own currency. The existing `holdings` list stays unchanged.
- **Missing FX rate:** if any lot of a position can't be converted to PLN, the position's PLN totals are null ("–" in the UI) and its lots still show their own-currency amounts.
- **Filters and sorting** above the list, in the style of the Transactions page: asset class, a search on name or ticker, sort by value, name, gain (PLN), gain % or purchase date (newest lot), ascending or descending. Filters don't change the summary tiles or the allocation chart.
- **Form placement:** the "Dodaj pozycję" button moves above the list and toggles the form card there, as on the Transactions page. "Edytuj" on a lot opens the same card filled in. The empty-wallet text no longer says the button is below.

## Out of scope

- Converting the purchase cost at the purchase-date FX rate. Cost stays converted at today's rate, so FX gains and losses are still ignored. This belongs to the later multi-currency work.
- Storing positions in the database or changing the holdings table. Grouping is computed on each request.
- Editing or deleting a whole position at once, and a "buy more" shortcut on the header.
- Sell transactions, realised gains and position history.
- Server-side filtering or sorting.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `portfolio`: new requirements for grouped positions (F22, F23) and for the Wallet positions list (filters, sorting, form placement).

## Impact

- **Backend:** `coffer.analytics.portfolio` gets a pure grouping function and lot amounts in their own currency. `HoldingInput` gains the purchase date. `coffer.portfolio` passes the purchase date in and adds `positions` to the summary schemas and router. No migration.
- **Frontend:** `PortfolioPage` (grouped expandable list, filter row, form at the top), a new `features/portfolio/list.ts` for filtering and sorting, `compareAmounts` moved from `features/transactions/list.ts` to `lib/`, `i18n/pl.ts`. Regenerate `openapi.json` and `schema.d.ts`.
- **Tests:** `tests/analytics/test_analytics.py`, `tests/portfolio/test_portfolio.py`, `PortfolioPage.test.tsx`, plus a vitest file for the new list helpers.
- **Docs:** `docs/architecture.md` if it describes the summary response; `docs/glossary.md` (position, lot).
- **Requirements:** F22, F23.
