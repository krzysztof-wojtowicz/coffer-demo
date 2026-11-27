# Tasks: ui-upgrades

Owners: **I-BE** backend implementer, **I-FE** frontend implementer, **T** tester (writes tests from the spec scenarios only, in the existing `tests/<module>/test_<module>.py` files). Groups 1–4 are backend, 5–8 frontend; the BE and FE implementers work on disjoint files. Run tests with your own DB: `COFFER_TEST_DB=coffer_test_<module>`.

## 1. Shared classes, target allocation, gap (I-BE, T)

- [x] 1.1 I-BE: add `coffer/analytics/allocation.py` with `ASSET_CLASSES`, the 9-row table, the redistribution chains, `target_allocation()` and `allocation_gap()` (design D1–D3). Verify that pyright and import-linter pass (`make lint`).
- [x] 1.2 I-BE: profile and portfolio models/schemas import the shared list. `ProfileOut` gains `target`. `PortfolioSummaryOut` gains the `target` block, built in `portfolio.service` via `profile.service`. Verify: `make openapi` shows one `AssetClass` enum.
- [x] 1.3 T: in `tests/analytics/test_analytics.py`, test every table row sums to 100, the spec's base and redistribution scenarios, longer horizon ⇒ equity not lower (property test over all risk/class combinations), the gap scenario (total 36), and gaps null for an empty portfolio. Verify: `make test-backend ARGS="tests/analytics"` passes.
- [x] 1.4 T: in `tests/profile/test_profile.py` and `tests/portfolio/test_portfolio.py`, test that `GET /api/profile` returns `target`, that old codes `stocks`/`deposit` get 422, and that the summary `target` is null without a profile and filled in with one. Verify: those test runs pass.

## 2. Display name (I-BE, T)

- [x] 2.1 I-BE: `User.display_name`, `RegisterIn`/`LoginIn` split, `UserOut.display_name`, `PATCH /api/auth/me` with the Polish 422 message (design D5). Verify: `make lint`.
- [x] 2.2 T: in `tests/accounts/test_accounts.py`, test that registration with a name returns 201, that a missing, blank or 51-character name returns 422 "Imię musi mieć od 1 do 50 znaków", that PATCH changes the name, that an invalid PATCH keeps the old name, and that PATCH without a session returns 401. Verify: `make test-backend ARGS="tests/accounts"` passes.

## 3. Remove category limits + migration 0012 (I-BE, T)

- [x] 3.1 I-BE: delete `analytics/limits.py`, `BudgetLimit` and the limits endpoints, schemas and service code, and the `limits` field of insights. Remove limits from `tests/budget`, `tests/analytics`, `test_security.py` and `conftest.py`. Verify: `grep -rni "budget_limit\|LimitStatus" src/backend/coffer` is empty (except migrations 0008 and 0012).
- [x] 3.2 I-BE: write `alembic/versions/0012_ui_upgrades.py` (design D10: delete all users, NOT NULL `display_name`, class mapping, drop `budget_limits`). Verify: `tests/test_migrations.py` upgrade → downgrade → upgrade passes with a single head, users that existed before 0012 are gone after upgrade, and the class mapping turns `deposit, cash, stocks` into `cash, stock` when run on its own.
- [x] 3.3 T: in `tests/budget/test_budget.py`, test that `/api/budget/limits` no longer exists (404/405, or 422 because it now matches `/{month}`) and that insights have no `limits` key. Verify: `make test-backend ARGS="tests/budget"` passes.

## 4. Price refresh in minutes, env cleanup (I-BE)

- [x] 4.1 I-BE: `price_refresh_minutes` (0–1440) replaces `price_refresh_hours` in `core/config.py`, `main.py` and `refresh_prices.fetch_stale`. Update the scheduler test in `tests/market`. Verify: `make test-backend ARGS="tests/market tests/core"` passes.
- [x] 4.2 I-BE: in `.env`, remove the Render/Gemini/LLM/agent lines (`COFFER_LLM_*`, `COFFER_OLLAMA_*`, `COFFER_AGENT_*`, the stale comment) and add `COFFER_PRICE_REFRESH_MINUTES=5`. In `.env.example`, document the variable with value 0. Verify: start the API, and within about 6 minutes the log or `market_quotes.fetched_at` shows a refresh.

## 5. Branding (I-FE)

- [x] 5.1 I-FE: redraw `Logo.tsx` as a single-colour (`fill-white`/`currentColor`) cup with one banknote. Make the "Coffer" wordmark white in `Layout` and `AuthPage`. Make `public/favicon.svg` the white glyph on a dark rounded square. Verify: `make check-web` passes, and visually check the login page, navbar and browser tab.

## 6. Account page: profile card and settings (I-FE)

- [x] 6.1 I-FE: in `ProfileSection`, remove the static `ALLOCATION`. The card shows horizon and risk, plus the target pie (`AllocationChart` target-only) from `profile.target` and the disclaimer. The edit form uses segmented horizon/risk controls and class chips from the shared `pl.assetClass` labels (design D6). Update `ProfileSection.test.tsx`. Verify: `make check-web`.
- [x] 6.2 I-FE: add the `SettingsRow` pattern. Rebuild `AccountPage` as profile → "Ustawienia" (name, password, opening balance, sessions, delete account), drop the "Bezpieczeństwo" header, and add the name to the registration form. The navbar shows `display_name` (always set). Update `AccountPage.test.tsx`, `AuthPage.test.tsx`, `Layout.test.tsx` and `OpeningBalanceSection.test.tsx`. Verify: `make check-web`.

## 7. Allocation chart with target, wallet layout (I-FE)

- [x] 7.1 I-FE: give `AllocationChart` the optional `target` prop with legend rows "52% · cel 34% · +18 pp" and the total gap footer, or the profile link when there is no profile (design D4). Use it in `PortfolioSummaryCard` and `PortfolioPage`. Add tests to `PortfolioSummaryCard.test.tsx` and `PortfolioPage.test.tsx` for the gap rendering and the no-profile case. Verify: `make check-web`.
- [x] 7.2 I-FE: reorder `PortfolioPage` (chart → table → "Dodaj pozycję" → hidden `HoldingForm`). Edit opens the form filled in and scrolls to it. Add a test: the form is hidden by default, the button shows it, and Edit shows it filled in. Verify: `make check-web`.

## 8. Filters and limits UI removal (I-FE)

- [x] 8.1 I-FE: add a `Select` `variant="ghost"` (borderless). Use it for the `TransactionsPage` filters and every other filter bar found with grep. Update `Select.test.tsx`. Verify: `make check-web`.
- [x] 8.2 I-FE: delete `LimitsSection(.test).tsx`. Remove limits from `SummaryPage`, `InsightsCard(.test)`, `budget/queries.ts` and `pl.ts`. Regenerate the types with `make openapi`. Verify: `grep -rni "limit" src/frontend/src/features` shows nothing related to budgets, and `make check-web` passes.

## 9. Docs and specs (docs-writer)

- [x] 9.1 Update `docs/data-model.md` (display_name, shared classes, no `budget_limits`), `architecture.md`, `development.md` and `glossary.md` (`COFFER_PRICE_REFRESH_MINUTES`, target allocation and gap), and `history.md`. Remove limits from `csv-format.md` if it mentions them. Remove "category spending limits" and F13/F14 from the budget spec Purpose. Verify: `grep -rni "limit" docs openspec/specs` has no hits for category limits, and `grep -rn "REFRESH_HOURS" .` is empty outside the archive.

## 10. Demo data and database reset (I-BE)

- [x] 10.1 I-BE: fetch daily closes for the chosen tickers for Sep–Oct 2026 with yfinance (one-off script in the scratchpad, not committed) and write the purchase prices into `seed_demo.py` as constants with a source/date comment. Rewrite the seed per design D11 (fixed dates, opening balance 2026-09-01, Sep–Nov transactions, holdings, profile, display name "Demo"). Update `tests/scripts`. Verify: `make test-backend ARGS="tests/scripts"` passes.
- [x] 10.2 Reset the local DB, then `make db-up && make migrate && make seed && make prices`. Verify: logging in as the demo user shows Sep–Nov transactions, a wallet valued at market prices, and a pie with the target and gap.

## 11. Integration check

- [x] 11.1 Run `make lint`, `make test-backend`, `make check-web`, `make openapi` (no diff afterwards) and `openspec validate --all --strict`. All must pass. Then run the reviewer agent on the diff.

## Workflow follow-up

- Archive the change with `openspec-archive-change` after review.
- Commit and open a PR from `change/ui-upgrades` only when the user asks.
