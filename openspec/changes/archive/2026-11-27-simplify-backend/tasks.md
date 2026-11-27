# Tasks

Owners: this is a **refactor** change (`orchestrate` refactor path). **implementer** agents own the groups, each on disjoint files. Group 1 runs first because the others build on it; groups 2–4 can then run in parallel. There is no separate tester: the existing tests are the safety net, and each group updates only the assertions its own removal changes. Record `wc -l` of `src/backend/coffer/**/*.py` before starting.

## 1. Core helpers (implementer A, owns `coffer/core/`)

- [x] 1.1 Add `Money` (input validation) and `MoneyStr` (two-decimal string output) annotated types to `coffer/core/money.py`, with one-line comments explaining each. Verify with a unit test in `tests/core/` that checks `"10.50"`, rounding with ROUND_HALF_UP, and rejection of NaN, negative values and 3 decimals.
- [x] 1.2 Add `get_owned(db, model, user_id, id)` to `coffer/core/db.py`. Verify that `make lint` passes.
- [x] 1.3 `coffer/core/config.py`: replace both list parsers with one `_split_list`; remove `allowed_origin_regex`, its grammar and validator, and `samesite=none` with its validator. `coffer/core/origin.py`: drop the regex branch. `coffer/core/db_url.py`: drop the `-pooler` special case and the Neon comments. Update `tests/core/` (remove the regex and pooler cases only), `.env.example` and the settings table in `docs/development.md`. Verify that `COFFER_TEST_DB=coffer_test_core make test-backend ARGS="tests/core"` passes.

## 2. Money and ledger modules (implementer B, owns `transactions`, `imports`, `cash`, `budget`, `analytics/month.py`, `scripts/seed_demo.py`, `alembic/versions/`)

- [x] 2.1 Add migration `0011_drop_tx_currency` that drops `transactions.currency` and `transactions.base_amount`; `downgrade()` re-adds them filled from `amount` / `'PLN'`. Remove both from the model, `seed_demo.py` and `TransactionOut`, and rename `TxView.base_amount` to `amount`. Verify with `make migrate`, `alembic downgrade -1`, `alembic upgrade head`, and `tests/test_migrations_e5.py` (one head).
- [x] 2.2 Switch the transactions, cash and budget schemas to `Money`/`MoneyStr` and `from_attributes`. Delete `_to_out`, `from_summary` and the local `fmt` helpers. Use `get_owned` in the transactions service. Verify that `make test-backend ARGS="tests/transactions tests/cash tests/budget tests/analytics"` passes with no assertion changes except the removed `currency` field.
- [x] 2.3 `imports`: reuse `transactions.service.UnknownCategoryError`, remove the double normalization in `dedup.py`, and translate the Polish comments. Verify that `make test-backend ARGS="tests/imports"` passes.

## 3. Portfolio and market (implementer C, owns `portfolio`, `profile`, `market`, `analytics/portfolio.py`, `scripts/refresh_prices.py`)

- [x] 3.1 `portfolio/schemas.py`: replace the 27 per-field serializers and `_money`/`_money_str` with `Money`/`MoneyStr` (plus a small `PctStr` if percent fields need one decimal). Verify that `make test-backend ARGS="tests/portfolio"` passes with no assertion changes.
- [x] 3.2 `portfolio/service.py`: import `coffer.market.service` directly (drop `_market()` and `MARKET_SERVICE`) and use `get_owned`. Keep the try/except around provider calls. Verify that `make test-backend ARGS="tests/portfolio tests/market tests/scripts"` passes, including the "market unavailable" cases.

## 4. Accounts (implementer A, after group 1; owns `accounts`)

- [x] 4.1 Remove the Vercel/Render notes from `accounts/ratelimit.py` (`client_ip` keeps the proxy-hops logic) and the `samesite=none` handling from `accounts/api.py`'s cookie code. Keep the comments that explain the atomic reservation. Verify that `make test-backend ARGS="tests/accounts"` passes.

## 5. Verification

- [x] 5.1 Run `make lint`, `make test-backend`, `make openapi`, `make check-web` (types changed only by `currency`) and `openspec validate simplify-backend --strict`. All must pass. Report the `wc -l` before and after in the change summary.

## Workflow follow-up

- Review with the `reviewer` agent: behaviour unchanged, the money format is identical, no assertions edited beyond the listed removals.
- Archive with `openspec-archive-change` (no specs to sync).
