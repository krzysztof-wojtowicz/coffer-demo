# Tasks

Refactor plus restyle, with no spec delta (see proposal.md). Per CLAUDE.md there is no separate tester: the existing frontend tests are the safety net. New pure helpers and the new chart get small unit tests from the implementer that builds them. Groups 1–4 run in order because each builds on the previous one. Inside group 3, tasks 3.2 and 3.3 touch disjoint feature folders and can go to two implementers in parallel. Run `cd src/frontend && npm test` and `npx tsc --noEmit -p tsconfig.app.json` after each group.

## 1. Remove theme switching (implementer A)

- [x] 1.1 Delete `lib/theme.ts`, `lib/theme.test.ts`, `components/ThemeToggle.tsx`, `components/ThemeToggle.test.tsx`, `public/theme-init.js`, `src/theme-init.test.ts`; remove `<ThemeToggle />` from `Layout.tsx` and the "Motyw" test from `Layout.test.tsx`; verify with `grep -rn "theme-init\|ThemeToggle\|useTheme" src/frontend` returning nothing
- [x] 1.2 Remove `pl.theme` from `i18n/pl.ts` and the `theme-init.js` script tag from `index.html`; delete the `:root[data-theme=…]` blocks in `index.css`, keeping `html { color-scheme: dark }`; verify `npm run typecheck` passes
- [x] 1.3 Reduce `theme-contrast.test.ts` to dark-only checks (drop the light-counterpart test and the `ThemeToggle` source import); verify `npm test` passes

## 2. Shared formatting and components (implementer A)

- [x] 2.1 Create `lib/format.ts` with `formatMoney(value, currency='PLN')`, `formatPct(value, {signed})` and `signOf(value)` (design §2), fold in `lib/money.ts`, and add `lib/format.test.ts` covering negative, zero (`"-0.00"`), null percentage, a non-PLN currency and an unknown currency fallback; verify the test passes
- [x] 2.2 Create `components/Signed.tsx` (design §3, including `kind="pct"` and `invert`) and make `Money` a thin, uncoloured wrapper over `formatMoney`; verify `npm test` passes
- [x] 2.3 Create `components/ui/Stat.tsx`, `components/ui/Bar.tsx` and `components/ui/BarList.tsx` (design §4), keeping `data-testid` and ARIA role pass-through; verify `npm run typecheck` passes
- [x] 2.4 Add short English comments to the new shared modules where intent is not obvious (string-only money rule, `signOf` zero handling); verify by reading the diff

## 3. Adopt shared pieces in features (implementers A and B, disjoint folders)

- [x] 3.1 (A) Replace the hand-built tiles and bars in `features/budget/SummaryTiles.tsx`, `InsightsCard.tsx` (`Change` → `Signed invert`, `LimitBar` → `Bar`), `LimitsSection.tsx` and `NetWorthCard.tsx` with `Stat`, `Signed`, `Bar` and `BarList`; verify the budget tests (`SummaryTiles`, `InsightsCard`, `LimitsSection`, `NetWorthCard`) pass unchanged or with only markup-query updates
- [x] 3.2 (B) In `features/portfolio/PortfolioPage.tsx`, remove the local `formatAmount`, `Pct` and inline gain-tone logic and use `formatMoney(v, ccy)`, `formatPct` and `Signed`; render the summary tiles with `Stat`; verify `PortfolioPage.test.tsx` passes
- [x] 3.3 (B) Replace the remaining `.replace('.', ',')` and inline sign logic in `features/transactions`, `features/import`, `features/cash`, `features/profile` and `features/auth`; simplify functions where duplication is obvious; verify `grep -rn "replace('.', ',')" src/frontend/src` returns only `lib/format.ts` and that `npm test` passes
- [x] 3.4 (A) `features/budget/PortfolioSummaryCard.tsx`: use `Stat`, `Signed`, and the shared formatters; verify `PortfolioSummaryCard.test.tsx` passes

## 4. New theme, fonts and charts (implementer A)

- [x] 4.1 Add `@fontsource-variable/geist` and `@fontsource-variable/geist-mono`, import them in `main.tsx`, set `--font-sans` and `--font-mono` (design §8), and apply `font-mono tabular-nums` in `Signed` and the `Stat` value; verify `npm run build` succeeds and the fonts appear in `dist/assets`
- [x] 4.2 Replace the tokens in `index.css` with the design §6 palette, add the `chart-1..7` tokens and the body dot-grid plus glow (design §7), and set `theme-color` in `index.html`; extend `theme-contrast.test.ts` with positive/negative-on-surface checks; adjust any failing values and record them in design §6; verify `npm test` passes
- [x] 4.3 Restyle the shared components per design §7: `Card` (borderless gradient, 6px radius, no title stripe), `Button`, `Input`/`Field`, `Select`, `DatePicker`, `ConfirmDialog`, `Badge`, `MonthPicker`, and the `Layout` header (sticky, blurred, no gold border); remove the now-unused per-file border classes in features; verify `npm test` passes
- [x] 4.4 Create `components/AllocationChart.tsx` (SVG donut + legend, `compact` prop, `role="img"` + `aria-label`, design §5) and use it in `PortfolioPage` (replacing `Allocation`) and `PortfolioSummaryCard`; add a test to `PortfolioPage.test.tsx` that checks the legend lists each class with its share and that the `aria-label` contains them; verify `npm test` passes
- [x] 4.5 Check the look in the running app (`make dev-web` against seeded data, `make seed`) on Summary, Transactions, Portfolio, Account and Login at desktop and ~375px widths; verify there is no horizontal overflow and that text is readable over the dot grid

## 5. Docs (docs-writer)

- [x] 5.1 Update `docs/architecture.md` §5: dark-only theme, semantic tokens incl. `chart-*`, shared `Stat`/`Bar`/`BarList`/`Signed`/`AllocationChart`, `lib/format.ts`, self-hosted Geist fonts; verify no remaining mention of theme switching in `docs/` except `history.md`
- [x] 5.2 Add a short entry to `docs/history.md` for this change; verify by reading the diff

## 6. Verification

- [x] 6.1 Run `make lint`, `make check-web` (tsc, vitest, build) and `openspec validate --all --strict`; all pass. `make test-backend` and `make openapi` are not needed (no backend or API changes); confirm `git diff --stat` shows no files under `src/backend/` or `openapi.json`

## Workflow follow-up

- Review with the `reviewer` agent (privacy, rules, no float money math introduced beyond the `signOf` comparison).
- Archive with `openspec-archive-change` after review; commit only when the user asks.
