# Design

## Context

What remains after `remove-ai-agent`: `accounts`, `transactions`, `imports`, `budget`, `cash`, `portfolio`, `profile`, `market` (quotes and FX), `analytics` (month, compare, limits, net_worth, portfolio, shares), `core`, `scripts`. The services are already thin. The repetition sits at the edges: schemas turning `Decimal` into strings, routers mapping rows to output models, ownership lookups, and configuration validation.

## Goals / Non-Goals

**Goals:**
- Fewer lines in `src/backend/coffer`, with one way to do each repeated thing.
- Every existing non-AI test still passes, with assertions changed only where this change removes something (the regex setting, the `currency` field).

**Non-Goals:**
- New layers such as a generic repository or a base CRUD router. They add more code than they remove at this size.
- Renaming modules or moving files between modules (CLAUDE.md layout stays).
- Merging tests (`consolidate-tests`).

## Decisions

1. **`Money` input type, `MoneyStr` / `PctStr` output types in `coffer.core.money`.** `MoneyStr` and `PctStr` (one decimal) are `Annotated[Decimal, PlainSerializer(...)]` types that serialize every output as a string, rounding ROUND_HALF_UP in a wide decimal context so huge values don't overflow. Output models hold `Decimal`, keep the "strings in JSON" rule, and can be built with `model_validate(obj, from_attributes=True)` instead of the hand-written `from_summary` / `_to_out` mappers. `Money` (non-negative input: finite, under the max, at most 2 decimals) is built with a label through a `money("<label>")` factory so error messages name the field; only portfolio uses it. Signed amounts (transactions, opening balance, budget limit inputs) keep their own validators and share the `MAX_ABS_AMOUNT` constant from `coffer.core.money`. Alternative: a shared `_money()` function in each schema. Rejected because it still repeats the decorator on every field.

2. **`get_owned(db, model, user_id, id)` in `coffer.core.db`.** It returns the row or `None`, and routers keep raising their own Polish 404 message. Alternative: raise `HTTPException` inside the helper. Rejected because services must not depend on FastAPI.

3. **The shared `UnknownCategoryError` lives in `transactions.service`.** `imports` already goes through that service (module boundary rule), so it reuses the same exception instead of defining its own.

4. **Direct import of the market service.** The `importlib` fallback guarded against a market module that might be missing. The module is always installed. Provider failures are still caught, and valuation still falls back to the manual value or cost, so the "works without market data" behaviour stays.

5. **Config: one `_split_list` helper; drop the regex grammar and `samesite=none`.** `allowed_origin_regex` existed only for Vercel previews; any future host can list its origins in `COFFER_ALLOWED_ORIGINS`. The origin format check (`_check_origin`) stays because it guards against a misconfiguration that would silently break the CSRF check. `cookie_samesite` keeps `lax` and `strict`.

6. **Drop `currency` and `base_amount`.** Today every write copies `amount` into `base_amount`, and every read uses `base_amount`. Analytics (`TxView.base_amount`) is renamed to `amount`. The migration downgrade re-adds both columns, filled from `amount`, so rollback keeps the data intact.

7. **Comments.** A module docstring is kept only where the module's role isn't obvious from its name. Inline comments explain constraints (PgBouncer, NUL bytes, ROUND_HALF_UP, atomic rate-limit reservation). Comments about deleted hosting are removed. Polish comments in code (for example in `bulk_create`) are translated.

## Risks / Trade-offs

- [`MoneyStr` changes the JSON format, such as `"10.5"` instead of `"10.50"` or a different exponent] → The serializer always calls `quantize` and formats with two decimals. The existing API tests assert exact strings, so they catch any difference.
- [`from_attributes` exposes a field by accident] → Output models list their fields explicitly; only the construction changes.
- [Removing `allowed_origin_regex` breaks someone's local `.env`] → Settings use `extra="ignore"`, so an old variable is ignored. Note it in `docs/development.md`.
- [The migration rewrites a large table] → It's local data only, and dropping a column is a metadata change in PostgreSQL.

## Migration Plan

Run `make migrate`. Roll back with `alembic downgrade -1` (the columns come back filled from `amount`) and `git revert`.
