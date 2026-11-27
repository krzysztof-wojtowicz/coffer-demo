# Proposal

## Why

Once the AI assistant is removed (`remove-ai-agent`), the remaining backend works, but it carries code that no longer pays for itself: helpers repeated by hand in every module, indirection added for the agent, configuration for one specific hosting setup (Vercel previews, Render, Neon) that no longer exists, and columns that always hold the same value. We want less code that is easier to read before we redeploy and rebuild the assistant. That means fewer lines, one way to do each thing, and English comments where the reason is not obvious.

## What Changes

Every behaviour in `openspec/specs/` stays the same. The changes are internal, plus a few settings and one response field.

- **Shared helpers:** one money type in `coffer.core.money` that validates input and serializes to a two-decimal string, replacing about 9 hand-written `f"{v:.2f}"` formatters and the per-field serializers in `portfolio/schemas.py`. One "get the user's row or 404" helper for the repeated `select(...).where(id, user_id)` lookups. One shared `UnknownCategoryError` instead of two. One list parser for comma or JSON env values in `config.py`.
- **Remove indirection:** `portfolio.service` imports `coffer.market.service` directly instead of through `importlib` (the market module is always present). `imports/dedup.py` stops normalizing keys a second time.
- **Hosting-specific configuration:** remove `COFFER_ALLOWED_ORIGIN_REGEX` and its regex grammar validator (used for Vercel preview URLs), `cookie_samesite=none` and its validator, the Neon `-pooler` special case in `core/db_url.py`, and the Vercel/Render notes in comments. **Kept** for any future deployment: the CSRF origin check with `COFFER_ALLOWED_ORIGINS`, the `COFFER_CORS_ENABLED` switch, `COFFER_COOKIE_SECURE`, `COFFER_TRUSTED_PROXY_HOPS`, the `postgres://` URL normalization, the body size limit, Argon2 and the rate limiter.
- **BREAKING (data model):** drop the `transactions.currency` and `transactions.base_amount` columns. The app is PLN only and `base_amount` always equals `amount`. `TransactionOut` loses its constant `currency: "PLN"` field. Analytics reads `amount`.
- **Comments:** short English comments on non-obvious decisions (why, not what). Remove comments that describe deleted hosting or history.

Out of scope:
- The AI assistant (`remove-ai-agent`), tests other than the ones the edited code needs (`consolidate-tests`), and the frontend beyond the generated types and the removed `currency` field.
- Changing any endpoint's path or behaviour, any rule in `CLAUDE.md`, or the price refresh paths (both `make prices` and the opt-in in-process thread stay).
- Multi-currency transactions. If they are needed later, they will come back as a feature with a spec.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none: no requirement changes (`skip_specs: true`). The transactions spec already says amounts are PLN; it never mentions a currency field. -->

## Impact

- Backend modules: `core` (money, config, db_url, origin comments), `accounts` (ratelimit comments, cookie settings), `transactions`, `imports`, `budget`, `cash`, `portfolio`, `analytics/month`, `scripts/seed_demo.py`.
- One new reversible migration (drop two transaction columns; `downgrade()` re-adds them and fills `currency='PLN'`, `base_amount=amount`).
- API: `TransactionOut.currency` is removed; `make openapi` regenerates `schema.d.ts`. The frontend does not read the field.
- Config: `COFFER_ALLOWED_ORIGIN_REGEX` and `COFFER_COOKIE_SAMESITE=none` are no longer accepted; update `.env.example` and `docs/development.md`.
- Depends on `remove-ai-agent` (no agent code left to update) and `agent-workflow-fix` (refactor path in `orchestrate`).
