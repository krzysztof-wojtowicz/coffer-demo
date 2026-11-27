# Tasks

Owners: **implementer A** (backend), **implementer B** (frontend), **tester** (backend tests from the spec, without reading the implementation). A and the tester run in parallel on disjoint files; B starts group 4 after 2.4 (`make openapi`). Groups 3 and 5 are frontend-only and can start at once.

## 1. Opening balance at start of day — implementer A

- [x] 1.1 In `src/backend/coffer/analytics/net_worth.py`, count transactions dated on `as_of` (`d >= as_of`) and update the docstring; verify with `COFFER_TEST_DB=coffer_test_cash make test-backend ARGS="tests/cash"` after 6.1
- [x] 1.2 Update `docs/data-model.md` (`opening_balances`: balance at the start of `as_of`) and `docs/glossary.md` (Net worth: transactions from that date on); verify by `grep -n "end of \`as_of\`" docs/` returning nothing
- [x] 1.3 Run `make seed` locally and check `GET /api/budget/net-worth` for the seeded user returns `cash_balance` "13317.06" (as of 2026-11-27, minus any transaction dated later)

## 2. Trend analytics and endpoint — implementer A

- [x] 2.0 Add `budget_income` to `MonthSummary` in `src/backend/coffer/analytics/month.py` (positive in-budget amounts, design §5), not exposed in `MonthSummaryOut`; verify `GET /api/budget/{month}` output is unchanged with `make lint` and the budget tests
- [x] 2.1 Add `src/backend/coffer/analytics/trend.py` with the dataclasses and `trend(summaries)` from design §5 (savings rate, averages over earlier months with data, per-category amounts/average/change, ordering); verify with `make lint`
- [x] 2.2 Add `service.trend(db, user_id, month, count)` in `src/backend/coffer/budget/service.py` reusing `month_summaries`; remove `month_insights` and `MonthInsights`; verify with `make lint` (import-linter, pyright)
- [x] 2.3 In `src/backend/coffer/budget/{api,schemas}.py` add `GET /api/budget/{month}/trend` with `months: Literal[3, 6, 12] = 6` and `TrendOut` (money as strings, percents as `PctStr`, nullable averages/changes); remove `/insights` and `InsightsOut`, `CategoryChangeOut`, `CategoryGrowthOut`; delete `src/backend/coffer/analytics/compare.py`; verify `curl` of the endpoint on the seeded DB returns 6 months oldest first
- [x] 2.4 Run `make openapi` and verify `openapi.json` and `src/frontend/src/api/schema.d.ts` list `/trend` and no `/insights`

## 3. Borderless controls, popover, holding form — implementer B

- [x] 3.1 Change `controlClass` in `src/frontend/src/components/ui/Input.tsx` to the borderless look with an `aria-invalid` ring (design §1); make `Select`'s `ghost` variant only add the off-default highlight; remove the `input-border` token if unused; verify login/register, transaction form and inline edit, holding form, settings (display name, password, opening balance, profile) and import show no borders, in `make dev-web`
- [x] 3.2 Where a control sits on a `surface-2` background, give it `bg-surface` via `className` so it stays visible; verify visually on each form from 3.1
- [x] 3.3 Rewrite `src/frontend/src/components/ui/popover.tsx` to flip above when there is more room there, clamp `maxHeight` to the available space with scrolling, clamp `left` to the viewport, and stay hidden until positioned (design §2); drop `max-h-64` in `Select.tsx`; extend `Select.test.tsx` with a case where the anchor is near the viewport bottom and the panel is placed above with a `maxHeight`, and verify with `make check-web`
- [x] 3.4 In `src/frontend/src/features/portfolio/HoldingForm.tsx` align the button cell with the input row (design §3); extend `HoldingForm.test.ts` only if a structural assertion is cheap; verify in the browser on the wallet page at `lg` and mobile widths, including that the asset-class dropdown can reach its last option

## 4. Summary page trends — implementer B (after 2.4)

- [x] 4.1 Add `useTrend(month, months)` in `src/frontend/src/features/budget/queries.ts`; remove `useInsights`; verify `tsc` via `make check-web`
- [x] 4.2 Rework `SummaryTiles.tsx` to four tiles (Przychody, Wydatki, Balans, Stopa oszczędności) fed by the trend's last month, each with a change vs the window average or "brak danych"; update `SummaryTiles.test.tsx`; verify with `make check-web`
- [x] 4.3 Add `TrendChart.tsx` (SVG income/expense columns per month, selected month highlighted, `sr-only` data table) and `CategoryTrends.tsx` (sparkline rows, this month / average / change, top 8 + "Pokaż wszystkie"); verify each with a vitest test rendering the seeded-shape data and checking labels and the table
- [x] 4.4 Update `SummaryPage.tsx` with the 3/6/12 window `Select` and the new cards; delete `InsightsCard.tsx` and `InsightsCard.test.tsx`; add the new strings to `pl.summary` and remove `insights*`, `colPrevMonth`, `colThisMonth`, `colChange*`, `topGrowth*`, `aboveAverage`, `byCategory` if unused; verify with `make check-web` and in the browser on the seeded data
- [x] 4.5 Update `pl.openingBalance.hint` to the start-of-day wording (design §4) and the `OpeningBalanceSection` test if it asserts the hint; verify with `make check-web`

## 5. Backend tests — tester (from `specs/budget/spec.md`, in parallel with groups 1–2)

- [x] 5.1 In `src/backend/tests/cash/test_cash.py`, change the "same day: inside opening" case so a transaction on `as_of` counts, and add the 5000 + 8500 − 264.15 = 13235.85 scenario and the "before `as_of` does not count" case
- [x] 5.2 In `src/backend/tests/analytics/test_analytics.py`, replace the `compare_months`/`top_growth` tests with `trend` tests: savings rate (56.3 example; unchanged by a ±1000.00 "Przelewy własne" pair while income becomes 9500.00; a positive "Inwestycje" counted in income but not in the rate; null with no in-budget income), averages over earlier months with data (4000/400/10.0 example, empty months skipped, null when none), category amounts with zero fill, out-of-budget excluded, new category (pct null), ordering, and the existing months-sum-to-cash property
- [x] 5.3 In `src/backend/tests/budget/test_budget.py`, replace the `/insights` tests with `/trend` tests: default 6 months oldest first, window across a year, 422 for `months=4` and a bad month, per-user isolation, 401 without a session, and `/insights` now returning 404

## 6. Verification — integrator

- [x] 6.1 Run `make lint`, `COFFER_TEST_DB=coffer_test_budget make test-backend`, `make openapi` (no diff after 2.4), `make check-web`, and `openspec validate --all --strict`; all pass
- [ ] 6.2 Manual pass in `make dev-api` + `make dev-web` on the seeded user: "Środki na kontach" shows 13 317,06 zł (less any later-dated transactions), all forms are borderless, the wallet asset-class dropdown shows every option, the holding form buttons line up with the inputs, and the summary page shows tiles, the column chart and category trends for 3/6/12 months

## Workflow follow-up

- Reviewer pass (`reviewer` agent), then `docs-writer` syncs `docs/` and specs.
- Archive with `openspec-archive-change` once merged-ready; commit only when the user asks.
