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
- F16: store savings goals (not implemented).
- F18: forecast the month-end balance.
- **AI assistant (F31–F38, N03):** removed during the refactor (see [history.md](history.md)); the requirements are currently unimplemented. It will be rebuilt for local LLMs after the refactor, as a new OpenSpec change designed from scratch.
- Duplicate warning when adding or editing a transaction manually.
- Real bank CSV formats (as configuration, not classes).

**Data model** ([data-model.md](data-model.md) §4)
- Naming conventions and a cascade schema test.
- Transaction integrity: category `code`, CHECKs, indexes.
- A shared asset-class vocabulary and `numeric(20,8)` unit prices.
- Multi-currency transactions (`fx_rates`, `user_settings`).
- Retention purge job.

**Security follow-ups** ([history.md](history.md#open-follow-ups-from-reviews))
- Decide the policy for requests with no `Origin` header.

**Release**
- Decide on hosting again once the refactoring is done (the previous Vercel + Render + Neon setup was removed; see [history.md](history.md)).
