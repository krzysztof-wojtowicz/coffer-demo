# Proposal

## Why

User feedback after `ui-upgrades`: form controls still use a bordered look that clashes with the borderless dark theme, the asset-class dropdown on the wallet page can open off-screen, the holding form's buttons sit below the input row, the cash total ignores transactions dated on the opening-balance day, and the summary page compares a month only with the previous one, which says little about spending trends.

The cash bug is concrete: the seeded user has an opening balance of 5 000,00 zł as of 2026-09-01, and the September salary (8 500,00 zł) and two purchases are dated 2026-09-01. Because the balance counts only transactions dated *after* `as_of`, those three are dropped, so "Środki na kontach" shows 5 081,21 zł instead of 13 317,06 zł (5 000,00 + 3 287,84 + 1 267,48 + 3 761,74).

## What Changes

- **Borderless form controls.** Every text input, select and date picker (login/register, transaction form and inline edit, holding form, settings, opening balance, import) uses the borderless look of the transactions-page filter bar: filled `surface-2` background, no border, an accent focus ring. Invalid fields stay visible through the ring/error text, not a border.
- **Dropdowns stay on screen.** The shared popover (used by `Select` and `DatePicker`) opens above its anchor when there is not enough room below, and limits its height to the visible space so its list scrolls. Fixes the asset-class dropdown on the wallet page.
- **Holding form layout.** The "Zapisz"/"Anuluj" buttons align with the input row, not with the hint text under it.
- **Opening balance is the balance at the start of `as_of`.** Transactions dated on `as_of` now count toward cash (`date >= as_of`). The settings hint says so. **BREAKING** (behaviour): users who entered an end-of-day balance will see that day's transactions counted again; they can move the date by one day.
- **Spending trends on the summary page.** New endpoint `GET /api/budget/{month}/trend?months=N` (N = 3, 6 or 12, default 6) returns, for the window ending at `month`: income, expenses, balance and savings rate per month (surplus over in-budget income, so transfers between own accounts and investment sales don't skew it); per in-budget category, its monthly amounts, window average and this month's change against that average; and window averages. All computed in `coffer.analytics`.
- **Simpler month section.** The month section becomes: stat tiles (income, expenses, balance, savings rate, each with a comparison to the window average), one "Przychody i wydatki" column chart over the window, and one "Kategorie w czasie" list where each category shows a sparkline, this month's amount, its average and the change. The previous-month table and the "Największe wzrosty" list are replaced by this list; the per-category bar chart of the month is replaced by the sparkline list's "this month" column.
- **BREAKING** (API): `GET /api/budget/{month}/insights` is removed; the trend endpoint covers F12 and F15.

## Out of scope

- New chart libraries: charts stay hand-written SVG like `AllocationChart`.
- Changing the transactions-page filters themselves, checkboxes, or the file picker in the import flow.
- Multiple bank accounts or per-account balances.
- Custom date ranges beyond 3/6/12 months; income per category trends.
- Light theme.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `budget`: "Opening balance" and "Net worth (F26)" change to count transactions on `as_of`; "Month comparison and top growth (F12, F15)" is replaced by a multi-month spending trend requirement with savings rate and window averages.

UI items 1–3 change presentation only and fix bugs against existing behaviour; no requirement text covers control styling or popover placement, so they need no spec delta.

## Impact

- Backend: `coffer/analytics/net_worth.py` (`cash_amounts` boundary), new trend functions in `coffer/analytics/` (replacing `compare.py`'s `compare_months`/`top_growth` use), `coffer/budget/{api,service,schemas}.py`; `openapi.json` and `src/frontend/src/api/schema.d.ts` regenerated.
- Frontend: `components/ui/{Input,Select,DatePicker,popover}.tsx`, `features/portfolio/HoldingForm.tsx`, `features/budget/*` (new trend card and charts, `InsightsCard` removed), `features/cash/OpeningBalanceSection.tsx` hint, `i18n/pl.ts`.
- Tests: `tests/budget/test_budget.py`, `tests/cash/test_cash.py` (same-day transaction now counts), `tests/analytics/`, frontend tests for the summary page, `Select`/popover and `HoldingForm`.
- Docs: `docs/data-model.md` ("valid at the end of `as_of`" → start), `docs/glossary.md`.
- Requirements: F10, F11, F12, F15, F26.
