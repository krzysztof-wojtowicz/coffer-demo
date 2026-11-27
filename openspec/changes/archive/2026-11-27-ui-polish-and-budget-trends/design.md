# Design

## Context

See proposal.md for motivation. Relevant current state:

- All form controls take their look from one string, `controlClass` in `components/ui/Input.tsx` (`border border-input-border` + `bg-surface-2`). `Select` and `DatePicker` reuse it; `Select` also has a `ghost` variant (`ghostClass`, no border) used by the transactions filter bar.
- `components/ui/popover.tsx` always places the panel at `anchor.bottom + 4` with `position: fixed`. `Select`'s list has a fixed `max-h-64`. A fixed panel that runs past the viewport bottom cannot be scrolled into view, which is the wallet-page bug: the holding form sits low on the page and the asset-class list has 8+ options.
- `HoldingForm` is a 4-column grid with `items-start`; every `Field` has a hint under the input, and the button cell uses `items-end`, so the buttons line up with the hints, not the inputs.
- `analytics/net_worth.py:cash_amounts` keeps `d > as_of`; `docs/data-model.md` documents the balance as "valid at the end of `as_of`". `tests/cash/test_cash.py::test_cash_uses_opening_balance` asserts a same-day transaction is excluded.
- `budget/service.py:month_summaries` already loads N months in one query and returns `MonthSummary` per month (with `surplus` and per-category `in_budget`). `analytics/compare.py` holds `compare_months` and `top_growth`, used only by `/insights`.
- No chart library is installed; `features/portfolio/AllocationChart.tsx` is a hand-written SVG.

## Goals / Non-Goals

**Goals:**
- One place decides control styling, so every form changes with a single edit.
- The popover fix works for every `Select` and `DatePicker`, not only the wallet page.
- Trend numbers are computed once, in `coffer.analytics`; the frontend only draws them.

**Non-Goals:**
- Reworking `Field`, `Button` or the filter bar.
- Caching or pre-aggregating monthly totals; a 12-month window is one indexed query.

## Decisions

### 1. Borderless controls by changing `controlClass`
Change `controlClass` to the filter look: `rounded bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-muted hover:brightness-125 focus:outline-none focus:ring-2 focus:ring-accent`, plus `aria-[invalid=true]:ring-2 aria-[invalid=true]:ring-negative` so invalid fields stay marked without a border. Then `ghostClass` equals `controlClass`; `Select`'s `ghost` variant keeps only its "moved off the default option → `text-accent`" behaviour. Check the `--input-border` token afterwards and remove it if nothing uses it.
*Alternative:* pass `variant="ghost"` at every call site — rejected, many call sites and easy to miss one.
Raw inputs that are not text fields (checkboxes, the hidden file input) are untouched.

### 2. Popover flips and clamps
In `popover.tsx`, measure the panel after render (`useLayoutEffect` on the panel ref) and compute:
- `spaceBelow = innerHeight - anchor.bottom - 8`, `spaceAbove = anchor.top - 8`;
- place below if the panel fits below or `spaceBelow >= spaceAbove`, otherwise above (`bottom = innerHeight - anchor.top + 4`);
- set `maxHeight` to the chosen space and `overflow-y: auto` on the panel; also clamp `left` so the panel stays inside the viewport width.
`Select` drops its own `max-h-64` in favour of `max-h-[min(16rem,100%)]`-style sizing via the panel's `maxHeight` (a list never taller than 16 rem, and never taller than the room available).
*Alternative:* a positioning library (Floating UI) — rejected, a new dependency for ~20 lines.

### 3. Holding form buttons
Give the button cell `self-start` and a top offset equal to a label line (`mt-6`, matching `Field`'s `text-sm` label + `gap-1`), so the buttons sit on the input row on wide screens; on one-column (mobile) layout they stay a full-width row below. A component test checks the classes are present; visual check is manual.
*Alternative:* move buttons to their own row under the grid — also fine, but the user asked for them on the same line as the inputs.

### 4. Opening balance at start of day
`cash_amounts` changes to `d >= as_of`. Nothing is stored differently, so no migration; the seed (`as_of = 2026-09-01`) then gives 13 317,06 zł. Update the settings hint (`pl.openingBalance.hint`) to: "Wpisz saldo z banku na początek wybranego dnia (przed transakcjami z tego dnia). Doliczamy transakcje od tego dnia włącznie." and the docs.
*Alternative:* keep end-of-day and only reword the hint — rejected, the user expects the opening day's salary to count, and start-of-day matches how people read "saldo na 1 września" when the month's transactions start that day.

### 5. Trend endpoint and analytics
New pure module `coffer/analytics/trend.py`:
- `MonthPoint(month, income, expenses, balance, surplus, savings_rate)`;
- `MonthSummary` (in `analytics/month.py`) gains `budget_income: Decimal` (positive in-budget amounts), computed in the same loop as `surplus`; it is not added to `MonthSummaryOut`;
- `Average(income, expenses, surplus, savings_rate)` and `Change(amount, pct)` (savings rate change in percentage points);
- `CategoryTrend(category_id, category_name, amounts: list[Decimal], average, change, change_pct)`;
- `Trend(month, months: list[MonthPoint], average: Average | None, change: TrendChange | None, categories: list[CategoryTrend])`;
- `trend(summaries: Sequence[MonthSummary]) -> Trend` taking summaries oldest first; the last one is `month`.

"Earlier months with data" = earlier summaries where income or expenses is non-zero. Savings rate = `surplus / budget_income * 100` (null when `budget_income` is zero) rounded to 0.1 (ROUND_HALF_UP, reusing `_pct` from `compare.py`, moved into `trend.py`). Category average divides by the same count of earlier months with data, so a category missing in one of those months counts as zero there.

`budget/service.py:trend(db, user_id, month, count)` calls `month_summaries` (already one query), reverses to oldest first and calls `analytics.trend`. Router: `GET /api/budget/{month}/trend` with `months: Literal[3, 6, 12] = 6` as a query param (FastAPI gives 422 for other values). `/insights`, `InsightsOut` and friends, and `analytics/compare.py` are removed along with their tests.
*Alternative:* return raw `MonthSummaryOut[]` and compute stats in the browser — rejected by the "totals only in analytics" rule.
*Alternative:* keep `/insights` alongside — rejected, two endpoints for overlapping numbers; nothing else consumes it.

Why `budget_income` and not `income`: the +1000 side of a transfer between own accounts, or a positive "Inwestycje" (an ETF sold to cash), is not earnings. `surplus` already ignores both categories, so dividing it by all income would understate the rate whenever such a transaction is imported (September seed: 50.4 % instead of 56.3 %). The Przychody/Wydatki tiles and chart keep `income`/`expenses` over all transactions, so months still add up to cash (N04).
*Alternative:* exclude those categories from `income` everywhere — rejected, it would break "monthly balances sum to cash" and change F10/F11.

### 6. Summary page layout
`SummaryPage` month section becomes:
1. Header: "Historia miesiąca", `MonthPicker`, and a ghost `Select` "3 / 6 / 12 mies." (state in the page, default 6).
2. `SummaryTiles` (existing `/api/budget/{month}` call is replaced by the trend's last month, so one request feeds the section): four tiles — Przychody, Wydatki, Balans, Stopa oszczędności — each with a small "vs średnia" line using `Signed` (expenses inverted). Null average → "brak danych".
3. `TrendChart` card "Przychody i wydatki": SVG column pairs per month (income `positive`, expenses `negative` tokens), selected month highlighted, month labels `MM.YY`, values in an accessible `<table class="sr-only">`. No axes beyond a baseline and a max label — that is the "simplified" chart.
4. `CategoryTrends` card "Kategorie w czasie": one row per category — name, inline SVG sparkline (`amounts`, last point emphasised), this month (`Money`), average, change (`Signed` inverted, ▲/▼). Top 8 rows, a "Pokaż wszystkie" toggle for the rest. Replaces the per-category `BarList`, the comparison table and "Największe wzrosty".
Empty month keeps the existing "Brak wydatków w tym miesiącu." text. All new strings go to `pl.summary`; `insights*`, `colPrevMonth`, `topGrowth*`, `aboveAverage` are removed.
The `frontend-design` skill guides styling; reuse `Card`, `Stat`, `Money`, `Signed`.

## Risks / Trade-offs

- [Existing opening balances become off by one day's transactions] → local-only app with seeded data; the hint states the rule; noted as BREAKING in the proposal.
- [Removing `/insights` breaks anything still calling it] → only `InsightsCard` uses it; `make openapi` regenerates types, and `tsc` fails on any leftover use.
- [Borderless inputs on `surface-2` can be low-contrast against a `surface-2` background (e.g. the legend box in `HoldingForm`, dialogs)] → check each form on its real background; where a control sits on `surface-2`, use `bg-surface` there via `className`.
- [Popover measuring after first paint can flicker] → measure in `useLayoutEffect` before paint; keep the panel `visibility: hidden` until positioned.
- [Sparklines with all-zero data] → draw a flat baseline; never divide by a zero max.

## Migration Plan

No schema change. Deploy order is irrelevant (local only): backend and frontend land together; run `make openapi` after the backend. Rollback = revert the commit.
