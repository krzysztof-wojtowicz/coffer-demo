# Design: wallet-grouped-positions

## Context

See proposal.md for the motivation. Current state that shapes the approach:

- A `Holding` row is one purchase (a lot): quantity, per-unit purchase price in `currency`, optional purchase date and manual value. There is no position entity.
- `coffer.analytics.portfolio.portfolio_summary` values each holding in PLN with today's FX rates (`fx_to_pln`). A holding whose currency has no rate stays in its own currency (`converted=False`) and is left out of the totals and the allocation. Cost is converted at today's rate too.
- `HoldingInput` carries no purchase date or creation time, so the analytics can't order lots or pick the newest name yet.
- Totals must be computed in `coffer.analytics` with `Decimal` only. The frontend may compare decimal strings (`compareAmounts` in `features/transactions/list.ts`) but must not add money.
- `PortfolioPage` renders `summary.holdings` and joins it with `GET /api/portfolio/holdings` by id to open the edit form. The form sits below the table.

## Goals / Non-Goals

**Goals:**
- One pure grouping function, unit-tested without a database.
- Lot amounts in the lot's own currency, so the expanded rows match what the user entered.
- Filtering and sorting in one small pure helper, tested in vitest, as on the Transactions page.

**Non-Goals:**
- No new table or migration. Positions are derived on each request.
- No change to how a single holding is valued in PLN.
- `holdings` in the summary and the `PortfolioSummaryCard` on the Summary page stay as they are.

## Decisions

### D1. Derived positions, not stored ones
Positions are computed from holdings on every summary request. The key is `symbol.strip().upper()`. A holding without a ticker gets the key `id:<holding id>`, so it forms its own position.

*Alternative:* a `positions` table with `holdings` as child lots. Rejected because it needs a migration, changes to the form and the API, and a rule for moving lots between positions. Grouping by ticker gives the same view with none of that.

### D2. Grouping in analytics
`HoldingInput` gains `purchase_date: date | None` and `created_at: datetime | None`, both defaulting to `None` so existing tests keep working. `portfolio_summary` also returns `positions: list[PositionValuation]`, built from the same per-holding valuations and the same `total_value` as the holdings, so header shares match the allocation.

- `PositionValuation`: `key`, `symbol`, `name`, `asset_class`, `quantity`, `cost`, `value`, `gain`, `gain_pct`, `share_pct`, `avg_price` (PLN amounts, null when any lot is unconverted), `latest_purchase_date` (for sorting), `lots`.
- **Name and class** come from the newest lot: the latest `purchase_date`, then the latest `created_at`, then the highest id.
- **Quantity** is the plain sum of lot quantities. It is shown even when the PLN totals are null.
- **Header money** is the sum of the lots' already-rounded PLN amounts. That way the header always equals the sum of what was valued, and `avg_price = quantize(cost / quantity)`.
- **Header share** is the sum of the position's value divided by `total_value`, rounded to 0.1 half-up. It is not the sum of the per-holding shares, which would add up rounding errors.
- **Position order** in the response is value descending, then key. The UI sorts again anyway.

### D3. Lot amounts in their own currency
`PositionLot` has: `holding_id`, `purchase_date`, `quantity`, `purchase_price`, `currency`, `cost`, `value`, `value_source`, `gain`, `gain_pct`. The router adds `as_of` from `result.quote_times[holding_id]`, the same way it does for `holdings`, so the stale-price note still works per lot. It is computed by a new `value_holding_native(h, fx)` next to `value_holding`, with the same fallback order:

- cost = `quantize(purchase_price × quantity)`;
- market price in the same currency → `quantize(price × quantity)`;
- market price in another currency → `quantize(price × quantity × rate(price_ccy) / rate(currency))`, only when both rates are known (PLN has rate 1);
- otherwise the manual value, otherwise the cost.

The value source can therefore differ from the PLN valuation only when a rate is missing. In that case the PLN valuation already falls back the same way, so both always agree. Because the PLN cost also uses today's rate, gain % is the same in both currencies.

*Alternative:* derive lot amounts in the frontend by dividing the PLN values by a rate. Rejected because the rates aren't in the response and the frontend must not do money arithmetic.

### D4. API shape
`PortfolioSummaryOut` gains `positions: list[PositionOut]`, and `PositionOut.lots: list[PositionLotOut]`. Money is sent as strings, quantities as `QtyStr`, percentages as `PctStr`, the same as `HoldingValuationOut`. The change only adds fields, so existing clients are unaffected. Run `make openapi` afterwards.

### D5. Frontend structure
- `features/portfolio/list.ts`: `PositionListOptions { assetClass, query, sortKey, sortDir }`, `defaultPositionOptions` (value, desc), `filterAndSortPositions(positions, opts)`. Null sort values go last in both directions; ties fall back to the key. Uses `compareAmounts`, moved to `lib/decimal.ts` and imported by both list modules.
- `PortfolioPage`:
  - The add button and form card come first, as on the Transactions page. "Edytuj" sets `editing` and opens the same card, scrolling up to it.
  - Then the summary tiles, the allocation chart, and the positions card with its filter row (ghost `Select`s plus a text input) and the list.
- **Positions list:** one `PositionRow` per position. The header is a `<button aria-expanded>` with a chevron. Expanded lots are nested rows showing the date, quantity, price, cost, value with its source badge, gain, and "Edytuj"/"Usuń". Lots get their `Holding` for the edit form from the existing `useHoldings` map by `holding_id`.
- **Expanded state** is kept per page as a `Set<string>` of position keys and is not saved between visits.
- **New Polish strings** go in `pl.portfolio`: filter labels, sort options, search placeholder, `emptyFiltered`, average price label, lot column headers, and the updated `empty` text.

## Risks / Trade-offs

- [Two lots with the same ticker but different asset classes, e.g. a typo] → They are still grouped, and the header shows the newest lot's class. The allocation chart still counts each holding under its own class, so it stays correct.
- [Totals become null for a whole position when one lot has no FX rate] → The existing `fx_missing` warning already explains this, and the lots stay visible in their own currencies.
- [The summary response roughly doubles in size (holdings + positions)] → Only for a single user's portfolio, which is small. `holdings` can be dropped later, once nothing reads it.
- [Cost at today's FX rate hides currency gains and losses] → This is already how it works and is listed as out of scope. Using the purchase-date rate is planned for the multi-currency work.

## Migration Plan

No database migration. The API change only adds fields. Rolling back means reverting the code.
