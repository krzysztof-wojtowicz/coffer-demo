# Design: ui-upgrades

## Context

See proposal.md for the motivation. Current state that shapes the approach:

- The target allocation is a static table in `ProfileSection.tsx`, keyed by risk only. Totals must live in `coffer.analytics`, so it has to move to the backend.
- The profile classes (`cash, deposit, stocks, etf, bonds, crypto, real_estate`) and the holding classes (`stock, etf, bond, real_estate, commodity, crypto, cash`) are two different lists, so they can't be compared.
- `users` has no name column. The Account page renders full `Card`s for each security action.
- The price thread exists (`market/scheduler.py`) but is off: `price_refresh_hours` is a whole-hour int that defaults to 0. `fetch_stale` re-fetches quotes older than `max_age`.
- The migration head is `0011_drop_tx_currency`.

## Goals / Non-Goals

**Goals:**
- One fixed, testable rule from profile to target allocation, as a pure function.
- The current-vs-target comparison is calculated once on the backend and shown by one shared chart component.
- The Account page reads as profile → settings, in the same visual style as the rest of the app.

**Non-Goals:**
- No financial advice engine: the tables are an illustrative model, labelled as such in the UI.
- No new chart library: the existing SVG `AllocationChart` is extended.

## Decisions

### D1. Shared asset-class list
The list is `stock, etf, bond, real_estate, commodity, crypto, cash`, in this order (used for sorting and tie-breaks). It is defined once in `coffer/analytics/allocation.py` as `ASSET_CLASSES`, and the profile and portfolio models and schemas import it. One shared `AssetClass` Literal is used in both schemas, so the OpenAPI shows a single enum. Polish labels live in `pl.ts` under a single `assetClass` map that the profile and wallet both use.

*Alternative:* keep `deposit` as its own class in holdings too. Rejected because deposits behave like cash for allocation, and an extra class clutters the pie.

### D2. Target allocation table
`analytics.allocation.target_allocation(horizon, risk, preferred) -> list[TargetShare]` (whole-number percents). The base table is hard-coded as nine rows, so nothing is rounded at runtime:

| risk / horizon | stock | etf | bond | cash | crypto | commodity | real_estate |
|---|---|---|---|---|---|---|---|
| low / short    |  1 |  9 | 70 | 20 | 0 | 0 | 0 |
| low / medium   |  3 | 22 | 60 | 10 | 0 | 5 | 0 |
| low / long     |  4 | 31 | 55 |  5 | 0 | 5 | 0 |
| medium / short |  6 | 19 | 55 | 20 | 0 | 0 | 0 |
| medium / medium| 11 | 34 | 40 | 10 | 0 | 5 | 0 |
| medium / long  | 15 | 45 | 22 |  5 | 3 | 5 | 5 |
| high / short   | 16 | 24 | 40 | 20 | 0 | 0 | 0 |
| high / medium  | 26 | 39 | 15 | 10 | 5 | 5 | 0 |
| high / long    | 30 | 45 |  3 |  5 | 7 | 5 | 5 |

How the table was built, so it can be explained:
- **Equity (stock + etf)** goes up with both risk and horizon: low 10/25/35, medium 25/45/60, high 40/65/75. A short horizon means less equity, because there's no time to recover from a drawdown. This is the standard glide-path idea behind target-date funds and age-based rules.
- **Single stocks** make up 10% / 25% / 40% of equity for low / medium / high risk. Stocks vs ETFs is a question of how concentrated the risk is, so it follows risk, not horizon. ETFs stay the diversified core.
- **Satellites** are small and only appear with longer horizons: commodity (gold) 5 from a medium horizon up; real estate (REIT) 5 for medium+ risk with a long horizon; crypto 3 (medium/long), 5 (high/medium), 7 (high/long).
- **Cash buffer:** 20 / 10 / 5 for short / medium / long horizons. **Bonds** take the rest.

**Redistribution.** The share of each unselected class moves along a fixed chain to the first *selected* class:

```
stock       -> etf -> bond -> cash
etf         -> stock -> bond -> cash
crypto      -> etf -> stock -> bond -> cash
real_estate -> etf -> bond -> cash
commodity   -> bond -> cash
bond        -> cash -> etf -> stock
cash        -> bond -> etf -> stock
```

Bond and cash fall back to equity, never to a satellite, so a low-risk user without bonds or cash does not end up mostly in gold. If no class in the chain is selected, the share goes to the selected class with the largest base share, with ties broken by list order. Every move lands on a selected class, so the order of moves doesn't matter and the result is deterministic. Output contains only selected classes with a share > 0, in list order.

*Alternative:* spread unselected shares proportionally over all selected classes. Rejected because it can push money into crypto when the user drops bonds.

### D3. Gap from target
`analytics.allocation.allocation_gap(current: list[ClassAllocation], target: list[TargetShare]) -> AllocationGap | None`. For each class that appears in either list, it returns `current_pct` (0.1 precision), `target_pct` and `gap_pp = current − target`. `total_gap_pp` is half the sum of |gap|, which is the share of the portfolio that would have to move to reach the target. It returns `None` gaps when the portfolio total is 0.

`portfolio.service` reads the profile through `profile.service.get()` (module boundary rule) and adds a `target` block to `PortfolioSummaryOut`:

```
target: {
  classes: [{asset_class, current_pct, target_pct, gap_pp | null}],
  total_gap_pp: str | null
} | null
```

`GET /api/profile` returns the plain target in `ProfileOut.target: [{asset_class, share_pct}]`.

### D4. Chart component
`AllocationChart` gets an optional `target` prop. Without it, it renders as it does today. With it, each legend row shows `52% · cel 34% · +18 pp`. The gap is coloured by size only (muted under 5 pp, warning at 5 pp or more), not by sign, because being over or under the target isn't good or bad in itself. A footer reads "Odchylenie od profilu: 36 pp". With no profile, the footer links to `/account` ("Ustaw profil inwestycyjny"). The profile card reuses the same chart in target-only mode (`allocation` = target shares).

### D5. Display name
New column `users.display_name VARCHAR(50) NOT NULL`. Accounts from before this change are deleted by the migration (D10), so no backfill and no e-mail fallback is needed; the navbar always shows the name. `Credentials` is split: `RegisterIn` (display_name, email, password) and `LoginIn` (email, password). `PATCH /api/auth/me` with `{display_name}` returns `UserOut`, which gains `display_name: str`. The field is trimmed, NUL characters are rejected, and the length must be 1–50. It is not rate-limited, since it isn't a credential endpoint.

### D6. Account page layout

```
[ Profil inwestycyjny ]   horizon + risk chips | pie (target) + legend   [Edytuj]
                          edit mode: segmented controls for horizon/risk,
                          class chips (toggle), Save / Cancel in card footer
[ Ustawienia ]
  Imię              Krzysztof                         >
  Hasło             zmienione 12.11.2026              >
  Saldo początkowe  5 000,00 zł od 1.09.2026          >
  Sesje             Wyloguj ze wszystkich urządzeń    >
  Usuń konto        (danger text)                     >
```

A new `SettingsRow` component (in `features/auth/`) is a button row that shows a label and the current value; clicking it expands the form in place. Only one row is open at a time, and Escape or Cancel closes it. The opening balance form moves into a row. Logout stays in the navbar. Horizon and risk use segmented buttons (`aria-pressed`) instead of radios, styled like `MonthPicker`.

### D7. Wallet layout
Order: status banners → tiles → allocation chart (with target) → positions table → "Dodaj pozycję" button → `HoldingForm` (only when open). "Edytuj" on a row opens the form with that holding filled in and scrolls it into view. Saving or cancelling hides it again.

### D8. Filters
The `Select` trigger gets a `variant="ghost"` style: no border, `bg-surface-2`, lighter on hover, accent ring on focus, accent text when the value is not the default. It is used in `TransactionsPage` filters and any other filter bars (found with a grep for `filter`). Form selects keep the bordered style.

### D9. Price refresh in minutes
`price_refresh_hours` is replaced by `price_refresh_minutes: int` (0–1440). The scheduler interval is `minutes * 60`, and `fetch_stale` takes `max_age=timedelta(minutes=...)`. The first run happens 60 s after startup, as today. `.env` gets `COFFER_PRICE_REFRESH_MINUTES=5`. `.env.example` documents it but keeps 0. `market_quotes` keeps one row per symbol and day, which is upserted on refresh, so the table doesn't grow every 5 minutes.

### D10. Migration 0012
One reversible revision, `0012_ui_upgrades`, which:
1. deletes every row of `users` (`ON DELETE CASCADE` removes all their data and sessions), then adds `users.display_name VARCHAR(50) NOT NULL`;
2. maps `investment_profiles.preferred_classes`: `stocks→stock`, `bonds→bond`, `deposit→cash`, de-duplicated (`cash`+`deposit` becomes one `cash`);
3. drops `budget_limits`.

The downgrade reverses the class mapping (`stock→stocks`, `bond→bonds`; `commodity` is dropped and `deposit` can't be restored), recreates an empty `budget_limits` with its original constraints, and drops the column; the deleted accounts cannot be restored. `0008` stays untouched. Step 2 runs on an empty table after step 1, but stays in the migration so it is correct on its own and documents the mapping.

### D11. Demo seed
`seed_demo.py` is rewritten with fixed dates, not relative to today:
- user "Demo", `demo@coffer.local`; opening balance on 2026-09-01;
- Sep–Nov 2026 transactions: salary, rent, bills, groceries, transport, leisure, a monthly "Inwestycje" transfer, plus a few one-offs, with a fixed RNG seed;
- 6–8 holdings across stock, etf, bond, crypto and commodity (for example a global ETF, a few GPW/US stocks, BTC, gold ETC, Polish treasury bonds as manual value). Purchase prices and dates are real daily closing prices from Sep–Oct 2026, fetched once with yfinance by the implementer and written into the script as constants with a comment giving the source and date;
- an investment profile (medium / long), so the gap shows straight away.

Removing `BudgetLimit` from the seed comes with the limits removal. Reset (there is no `db-reset` target, and none is added): `make db-down` with the volume removed (or drop and recreate the `coffer` database), then `make db-up && make migrate && make seed && make prices`.

## Risks / Trade-offs

- [Yahoo rate limiting at a 5-minute interval] → only stale or held symbols are fetched, the advisory lock prevents parallel runs, failures are logged and the next run retries. Can be raised to 15 if throttled.
- [Breaking `PUT /api/profile` codes] → the frontend and backend ship together on one branch, and the migration maps stored data.
- [The allocation table looks like advice] → the card says "Model poglądowy, nie stanowi porady inwestycyjnej".
- [Hard-coded historical prices go stale] → that's intended: they are purchase prices, and current values come from live quotes.
- [Migration 0012 deletes every existing account] → intended: the project is local-only, the DB is reset and re-seeded right after, and the demo account is recreated with a name.
- [The downgrade loses `commodity` from profiles and `deposit` as a separate class] → acceptable for a local-only project, and documented in the migration.

## Migration Plan

Work on branch `change/ui-upgrades`. After implementation: reset the local DB, `make migrate`, `make seed`, `make prices`, run the API with the 5-minute refresh. Rollback is `alembic downgrade 0011`.
