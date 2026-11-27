# Roadmap

What's left. Planned work with a spec lives in [`openspec/changes/`](../openspec/changes) (`openspec list`); this page is the backlog of ideas that don't have a change yet. To start one, create a change with the `openspec-propose` skill.

## Active changes
| Change | Summary |
|---|---|
| `add-transaction-server-filtering` | Server-side filters, sorting and paging of transactions (breaking response shape) |
| `improve-ui-kit-accessibility` | Keyboard and ARIA support in `Select`, `DatePicker`, `ConfirmDialog`, popover |
| `add-net-worth-history` | Monthly cash-balance chart on the summary page |
| `add-e2e-playwright` | Browser tests of key flows (after the filtering change) |

## Backlog
**Product (priority C, from the requirements)**
- F09: export all user data to CSV (also the "export before deleting the account" path).
- F16: store savings goals (today only a `budget_plan` parameter).
- F18: forecast the month-end balance.
- F38: chat with the agent about the user's data.
- Duplicate warning when adding or editing a transaction manually.
- Real bank CSV formats (as configuration, not classes).

**Data model** ([data-model.md](data-model.md) §4)
- Naming conventions and a cascade schema test.
- Transaction integrity: category `code`, CHECKs, indexes.
- A shared asset-class vocabulary and `numeric(20,8)` unit prices.
- Multi-currency transactions (`fx_rates`, `user_settings`).
- Retention purge job.

**Agent and security follow-ups** ([history.md](history.md#open-follow-ups-from-reviews))
- Stop the model call when the SSE client disconnects; handle the SSE `error` event in the UI.
- Tighten the number validator.
- Decide the policy for requests with no `Origin` header.

**Release**
- Manual pass over all six actions with and without a local model, and over limits and "Oceń zakup".
- Redeploy the backend on Render with migrations `0007`–`0009` ([deploy/release-checklist.md](deploy/release-checklist.md)).
