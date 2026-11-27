# Tasks: wallet-grouped-positions

Owners: **I-BE** backend implementer, **I-FE** frontend implementer, **T** tester (writes tests from the spec scenarios only, in the existing test files). Groups 1–2 are backend, 3–4 frontend; BE and FE implementers work on disjoint files. Run backend tests with your own DB: `COFFER_TEST_DB=coffer_test_<module>`. The frontend starts once 2.1 has regenerated `schema.d.ts`.

## 1. Grouping and own-currency lots in analytics (I-BE, T)

- [x] 1.1 I-BE: in `coffer/analytics/portfolio.py`, add `purchase_date` and `created_at` (default `None`) to `HoldingInput`, add `value_holding_native`, the `PositionLot` and `PositionValuation` dataclasses, and `positions` on `PortfolioSummary`, built as in design D1–D3 (ticker key, newest name and class, PLN totals null when any lot is unconverted, header share from the position value, lots ordered by date with undated last). Verify: `make lint` passes.
- [x] 1.2 T: in `tests/analytics/test_analytics.py`, test the spec scenarios "Same ticker grouped", "Ticker case and spaces ignored", "Holding without a ticker", "Different currencies grouped", "Newest name", "Totals of a position", "Lot without an FX rate", "Foreign-currency lot", "Quote in a different currency than the lot" and "Lot order". Verify: `COFFER_TEST_DB=coffer_test_analytics make test-backend ARGS="tests/analytics"` passes.

## 2. Summary API (I-BE, T)

- [x] 2.1 I-BE: `portfolio/service.py` passes `purchase_date` and `created_at` into `HoldingInput`. `portfolio/schemas.py` gets `PositionOut` and `PositionLotOut`, and `PortfolioSummaryOut.positions`. The `/summary` router maps the positions and fills each lot's `as_of` from `quote_times` (design D4). Run `make openapi`. Verify: `make lint` passes, and `schema.d.ts` contains `PositionOut`.
- [x] 2.2 T: in `tests/portfolio/test_portfolio.py`, test that `GET /api/portfolio/summary` returns `positions` with grouped lots for two holdings with the same ticker in different case, money as strings, one position per holding without a ticker, and only the caller's holdings (another user's AAPL never joins the group). Verify: `COFFER_TEST_DB=coffer_test_portfolio make test-backend ARGS="tests/portfolio"` passes.

## 3. List helpers (I-FE, T)

- [x] 3.1 I-FE: move `compareAmounts` to `src/frontend/src/lib/decimal.ts` and import it in `features/transactions/list.ts` (keep re-exporting it from there if any test imports it). Add `features/portfolio/list.ts` with `PositionListOptions`, `defaultPositionOptions` (value, desc) and `filterAndSortPositions` (asset class, case-insensitive name/ticker search, sort by value, name, gain, gain %, latest purchase date, nulls last in both directions; design D5). Verify: `make check-web` passes.
- [x] 3.2 T: add `features/portfolio/list.test.ts` covering the "Filter by asset class", "Search" and "Sort by gain" scenarios, plus nulls-last for descending and ascending. Verify: `make check-web` passes.

## 4. Wallet page (I-FE, T)

- [x] 4.1 I-FE: rebuild `PortfolioPage`: the "Dodaj pozycję" toggle button and form card at the top ("Edytuj" opens it filled in and scrolls to it), then the tiles and chart, then the positions card with the filter row (ghost `Select`s and a search input) and `PositionRow`s. Headers are collapsed `aria-expanded` buttons showing PLN totals and "–" for null. Lots show own-currency amounts, the value-source badge and the stale-price note, with "Edytuj" and "Usuń" (design D5). Add the new strings to `pl.portfolio`, including `emptyFiltered` "Brak pozycji spełniających filtry." and the updated `empty` text ("…przyciskiem powyżej."). Verify: `make check-web` passes, and in `make dev-web` the demo wallet shows grouped positions.
- [x] 4.2 T: in `PortfolioPage.test.tsx`, test "Expand a position", "Single-lot position", "Edit a lot", "Filter by asset class" (the total-value tile is unchanged), "Nothing matches", "Open and close the form" and "Empty wallet". Replace any old test that assumed one table row per holding or the button below the table. Verify: `make check-web` passes.

## 5. Docs (docs-writer)

- [x] 5.1 Add "position" and "lot" to `docs/glossary.md`. Describe `positions` in the summary response wherever `docs/architecture.md` describes the summary. Add a `docs/history.md` entry. Verify: `grep -n "position" docs/glossary.md` shows the new entries.

## 6. Integration check

- [x] 6.1 Run `make lint`, `make test-backend`, `make check-web`, `make openapi` (no diff afterwards) and `openspec validate --all --strict`. All must pass. Then run the reviewer agent on the diff.

## Workflow follow-up

- Archive with `openspec-archive-change` after review. Commit only when the user asks.
