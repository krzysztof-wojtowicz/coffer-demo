# Proposal: ui-upgrades

## Why

After the UI refactor the app looks consistent, but several parts are still rough. The investment profile gives a static target allocation that ignores the horizon and merges stocks with ETFs. The user can't see how their wallet compares with that target. The Account page is a stack of full cards. Category limits are a feature nobody uses. The demo account doesn't reflect real market data. This change finishes the new layout and makes the profile actually useful.

## What Changes

- **Branding:** a new single-colour white logo (a coffee cup with one banknote) and a white "Coffer" wordmark on the login page and in the navbar. The favicon is the white logo on a dark rounded square.
- **One asset-class list:** the profile and holdings share `stock`, `etf`, `bond`, `crypto`, `real_estate`, `commodity`, `cash`. **BREAKING** for `PUT /api/profile`: the codes `stocks`, `bonds` and `deposit` are gone. A data migration maps existing profiles (`deposit` → `cash`).
- **Target allocation:** calculated on the backend from risk × horizon, with shares from unselected classes moved to similar classes. `GET /api/profile` returns it. The profile card on the Account page becomes simpler, merges in the target allocation and shows it as a pie chart. The edit form gets a cleaner style.
- **Current vs target:** `GET /api/portfolio/summary` returns the target share and the gap in percentage points for each class, plus a total gap. The pie chart widget on the Summary and Wallet pages shows these next to each class.
- **Display name:** entered at registration (required), changeable later, and shown in the navbar in place of the e-mail. **BREAKING:** migration 0012 deletes every existing account (and its data), so every remaining account has a name.
- **Settings section** on the Account page, below the profile. Name, password, opening balance, sessions and account deletion become collapsed rows that open in place. The "Bezpieczeństwo" header goes.
- **Wallet layout:** the pie chart first, then the positions table, then an "Add position" button that opens the hidden form at the bottom. Editing a position opens the same form.
- **Filter controls:** borderless dropdowns in the current theme everywhere they are used.
- **BREAKING:** category limits (F13, F14) are removed: endpoints, insights field, UI, tests and docs. The `budget_limits` table is dropped by a new migration.
- **Price refresh:** the in-process refresh runs every `COFFER_PRICE_REFRESH_MINUTES` (replaces `COFFER_PRICE_REFRESH_HOURS`), set to 5 for local dev. Leftover Render/Gemini/LLM/agent settings are removed from `.env`.
- **Demo data:** the database is reset and the demo account is re-seeded. It gets an opening balance on 1 Sep 2026, made-up transactions for September–November 2026, and holdings bought at real historical closing prices.

## Out of scope

- Rebalancing suggestions (what to buy or sell to reach the target).
- Editing the allocation tables in the UI; they stay fixed in code.
- Changing the e-mail address.
- Holding history or charts of portfolio value over time.
- The parked changes (`add-net-worth-history`, `add-transaction-server-filtering`, …).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `accounts`: registration takes a display name. A new requirement lets the user change it. Account deletion no longer lists limits.
- `budget`: Category limits (F13, F14) are removed.
- `portfolio`: Manage holdings and Investment profile (F30) use the shared asset-class list. New requirements cover the target allocation and the gap from target. Price refresh (F25) is set in minutes.

## Impact

- **Backend:** `accounts` (model, schemas, register, new `PATCH /api/auth/me`), `profile` (classes, target), `portfolio` (summary with target and gap), `analytics` (new target and gap functions; `limits.py` deleted), `budget` (limits removed), `core/config.py` and `main.py` (refresh setting), `scripts/seed_demo.py`.
- **Migrations:** 0012 adds `users.display_name`, maps profile classes and drops `budget_limits`. It is reversible and keeps one head.
- **Frontend:** `Logo`, `Layout`, `AuthPage`, `AccountPage`, `ProfileSection`, `AllocationChart`, `PortfolioSummaryCard`, `PortfolioPage`, `HoldingForm`, `Select`, `TransactionsPage`, `SummaryPage`, `InsightsCard`, `LimitsSection` (deleted), `i18n/pl.ts`, `public/favicon.svg`. Regenerate `openapi.json` and `schema.d.ts`.
- **Docs:** `data-model.md`, `architecture.md`, `development.md`, `glossary.md`, `.env.example`.
- **Requirements:** F01, F13, F14, F25, F30.
