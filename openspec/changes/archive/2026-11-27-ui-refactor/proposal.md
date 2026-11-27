# Proposal

## Why

The backend refactor is done; the frontend still carries a light/dark/system theme switch that nobody needs, the same formatting and chart markup copied across features, and a gold, bordered look that feels heavy. Now is the time to make the frontend smaller and easier to change, and to give the app a cleaner, more modern dark look, before new features (the local-LLM assistant, net-worth history) land on top of it.

## What Changes

- **BREAKING (UI):** remove theme switching. The app is dark only: delete `ThemeToggle`, `lib/theme.ts`, `public/theme-init.js`, the light token block in `index.css`, the `pl.theme` strings and their tests. The "Motyw" radiogroup disappears from the header.
- Deduplicate the frontend:
  - one formatting module (`lib/format.ts`) for money in any currency, percentages with Polish decimal comma, and sign detection; it replaces 12 inline `.replace('.', ',')` calls, the local `formatAmount` in `PortfolioPage`, and the sign regexes in `SummaryTiles`;
  - one `Signed` component for sign-coloured amounts and percentages (replaces `Money colored`, `Pct`, and inline tone logic);
  - shared `Stat` (label + value + optional delta), `Bar` and `BarList` components, which replace the stat tiles and progress-bar markup copied in `SummaryTiles`, `InsightsCard`, `PortfolioPage` and `PortfolioSummaryCard`;
  - one `AllocationChart` used on both the Portfolio page and the Summary card.
  - Simplify functions along the way and add English comments where the intent is not obvious.
- New visual theme ("night ledger"): a darker background with a subtle dot-grid pattern, borderless cards with a soft vertical gradient and a smaller radius, an indigo-violet accent instead of gold, darker green and red for income and expenses, and the Geist / Geist Mono font pair, self-hosted.
- Better charts: portfolio allocation becomes an SVG donut with a legend; category spending and limits become slimmer bar lists that use the shared components. The charts are hand-rolled SVG and add no chart library.

No data, API or calculation changes. Amounts are still strings from the API and are only formatted, never summed (N06 Polish UI unchanged; all visible text stays in `i18n/pl.ts`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. No requirement in `accounts`, `transactions`, `budget` or `portfolio` covers theming or visual style, and every displayed value, label and flow stays the same. The change sets `skip_specs: true`.

## Impact

- `src/frontend/src/index.css`, `index.html`, `public/theme-init.js`
- `src/frontend/src/components/**` (`Layout`, `Money`, `ThemeToggle`, `Logo`, `ui/*`) and new shared components
- `src/frontend/src/features/{budget,portfolio,transactions,import,auth,profile,cash}/**`: adopt the shared formatting and components
- `src/frontend/src/lib/{theme,money}.ts` → `lib/format.ts`
- Tests: theme tests deleted; `theme-contrast.test.ts` reduced to dark-only checks; existing component tests are the safety net and are updated only where markup or the theme toggle changed
- Dependencies: add `@fontsource-variable/geist` and `@fontsource-variable/geist-mono` (self-hosted fonts, no CDN, works offline). No chart library.
- Docs: `docs/architecture.md` §5 (shared UI components, dark-only theme). The parked `improve-ui-kit-accessibility` gets a note that only one theme remains.

## Out of scope

- New features, new pages, routing or navigation structure changes
- Backend, API and `openapi.json` changes
- The keyboard and screen-reader work in the parked `improve-ui-kit-accessibility` change (existing ARIA roles are kept, not extended)
- Charts over time (net-worth history), which belong to the parked `add-net-worth-history`
- A mobile-specific redesign beyond keeping the current responsive behaviour working
