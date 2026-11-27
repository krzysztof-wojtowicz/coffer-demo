# Design

## Context

See proposal.md – Why. Current state that shapes the approach:

- Tailwind v4 with semantic tokens in `index.css` (`@theme` block: `bg`, `surface`, `surface-2`, `border`, `accent`, `positive`, `negative`, …). Components use only these tokens, so changing the palette is mostly a token edit.
- Theme switching is spread over `lib/theme.ts`, `components/ThemeToggle.tsx`, `public/theme-init.js`, a `:root[data-theme="light"]` block, `pl.theme`, and four test files (about 850 lines in total).
- `theme-contrast.test.ts` reads `index.css` as raw text and checks contrast ratios and badge tones. It also checks that every dark token has a light counterpart, and that check goes away with the light theme.
- No chart library is installed. Every "chart" is a `div` bar (`h-2 rounded-full bg-surface-2` + an inner `bg-accent` div), copied 4 times.
- The API returns amounts and percentages as decimal strings (`"-12.50"`, `"62.4"`); the frontend only formats them.

## Goals / Non-Goals

**Goals:**
- One place for each concern: formatting (`lib/format.ts`), sign colour (`Signed`), stat tile (`Stat`), progress bar (`Bar` / `BarList`), allocation (`AllocationChart`).
- Restyling should be token and component edits; feature files should hold no colour or radius decisions beyond layout.
- Existing tests keep passing, changed only where markup or the theme toggle really changed.

**Non-Goals:**
- A general chart library or a design-system package.
- Changes to i18n structure (strings stay in `pl.ts`; only `pl.theme` is removed and chart labels are added if needed).

## Decisions

### 1. Order: delete, extract, restyle, chart
Delete the theme code first, so there is less to keep working. Then extract the shared pieces while the old look is still in place, so the existing tests confirm that behaviour hasn't changed. Only then change tokens and component styles, and finally replace the allocation bars with the donut. If we restyled first, every duplicated copy would have to be restyled and then removed.

### 2. Formatting module `lib/format.ts`
```
formatMoney(value: string, currency = 'PLN'): string   // Intl pl-PL, falls back to "<value> <ccy>"
formatPct(value: string | null, opts?: { signed?: boolean }): string  // "62,4%", "+3,1%", "–" for null
signOf(value: string): -1 | 0 | 1                       // string-based; "-0.00" counts as 0
```
- `signOf` parses the string with `Number` only to compare it with zero; display values always come from the API string. This keeps the rule that the frontend never sums or derives amounts.
- One `Intl.NumberFormat` is cached per currency.
- `lib/money.ts` is folded into this module and its imports are updated.
- Alternative considered: keep `money.ts` and add `pct.ts`. Rejected because sign handling is shared between the two and would end up duplicated again.

### 3. `Signed` component
`<Signed value="-12.50" />` for money, `<Signed value="3.1" kind="pct" />` for percentages, and an `invert` prop for places where an increase is bad (spending change in `InsightsCard`, which uses `warning` for up and `positive` for down today). It renders `+` for positive values when signed, uses `text-positive`, `text-negative` or nothing, and is always `tabular-nums`. It replaces `Money colored`, `Pct`, the gain cell logic, and the balance regex in `SummaryTiles`. A plain `Money` (no colour) remains as a thin wrapper, or uses `formatMoney` directly.

### 4. `Stat`, `Bar`, `BarList`
- `Stat({ label, value, delta?, testId? })`: muted label, large mono value, optional delta line below. It replaces the 3 hand-built tile grids and keeps the `data-testid="tile-*"` attributes the tests rely on.
- `Bar({ pct, tone?, label, role? })`: a single track and fill, with width clamped to 0–100, and the ARIA role passed through (`meter` for allocation, `progressbar` for limits) so the current semantics stay. Track height goes from `h-2` to `h-1.5`, with `rounded-sm` ends.
- `BarList({ items: { key, label, value: ReactNode, pct, tone? }[] })`: label on the left, value on the right, bar underneath. Used by budget categories and the `LimitBar` list.

### 5. `AllocationChart` (hand-rolled SVG donut)
- An SVG `circle` ring with one `stroke-dasharray` segment per asset class and a small gap between segments. The centre shows the total value, or the largest share. On the right (stacked on mobile) is a legend with a swatch, the class name, the share and the value.
- `compact` prop: the Summary card shows the ring and the legend with shares only. The Portfolio page also shows values.
- Accessibility: `role="img"` with an `aria-label` that lists the classes and their shares. The legend is real text, so the data stays readable without the graphic.
- Colours: a fixed categorical list of 7 tokens (`--color-chart-1..7`: violet, teal, sky, rose, amber, slate, lime), assigned by asset-class order so a class always gets the same colour.
- Alternative considered: Recharts or visx. Rejected because the donut and bars are about 60 lines of SVG, a library adds around 100 kB and a second styling system, and the only line or area chart we foresee (net-worth history) is parked. We can reconsider when that change resumes.

### 6. Visual tokens ("night ledger")
| Token | Value | Notes |
|---|---|---|
| `bg` | `#0b0c10` | darker than today's `#15171c` |
| `surface` / `surface-2` | `#14161d` / `#1b1e27` | card gradient runs from `surface` to `bg` |
| `border` | `rgb(255 255 255 / 0.06)` | hairlines only (table rows, inputs) |
| `input-border` | `#6a7088` | inputs keep a visible edge |
| `text` / `muted` | `#e6e7ee` / `#8b8fa3` | |
| `accent` / `accent-strong` / `accent-soft` | `#8e7ef3` / `#4637b0` / `rgb(142 126 243 / 0.08)` | indigo-violet; `accent` is the light text/fill tone, `accent-strong` is the solid fill under white text (primary button, selected day/month); one value cannot serve both at 4.5:1 |
| `positive` | `#36ab78` | darker emerald, lightened from `#2e9e6e` for the success Badge |
| `negative` | `#e0707a` | muted crimson, lightened from `#c4525a` to reach 4.5:1 on `surface` |
| `warning` / `info` | `#c98a2e` / `#6f9bd8` | |
| `chart-1..7` | violet `#6b4fe6`, teal `#2fb5a3`, sky `#4fa3e0`, rose `#e0708f`, amber `#d9a441`, slate `#646b80`, lime `#8fc84f` (one per asset class) | checked for mutual distinguishability |

These values are a starting point. The contrast test decides: body text ≥ 4.5:1 on `bg` and `surface`, primary-button text ≥ 4.5:1 on `accent`, and positive/negative ≥ 4.5:1 on `surface`. If a value fails, it is lightened in place and the new value goes into this table.

### 7. Surfaces, background, shape
- **Background:** `body` gets `radial-gradient(rgb(255 255 255 / 0.045) 1px, transparent 1px)` at `20px 20px` with `background-attachment: fixed`, plus a soft violet glow at the top (a large, low-opacity `radial-gradient` of the accent). It is pure CSS with no image asset.
- **Card:** no border, `rounded-md` (6px instead of 12px), `bg-linear-to-b from-surface to-surface/60`, a 1px inner top highlight (`inset 0 1px 0 rgb(255 255 255 / 0.04)`), and a soft drop shadow. The `border-l-2 border-accent` title stripe goes; titles become a smaller, medium-weight, muted uppercase label or a plain semibold heading.
- **Header:** sticky, `bg-bg/70 backdrop-blur`, no bottom border, just a hairline. The active nav item uses `accent-soft` with accent text.
- **Inputs and buttons:** `rounded` (4px); the primary button uses solid `accent-strong` with white text. Secondary buttons lose their border and use `surface-2`.
- **Tables:** no header border; row hairlines use `border`, and rows get a hover tint of `surface-2/50`.

### 8. Fonts
`@fontsource-variable/geist` and `@fontsource-variable/geist-mono` are imported once in `main.tsx`. `--font-sans: 'Geist Variable', ui-sans-serif, …` and `--font-mono: 'Geist Mono Variable', ui-monospace, …`. Amounts (`Signed`, `Stat` values, table numeric cells) use `font-mono tabular-nums`. Self-hosting keeps the app working offline and sends no requests to a font CDN. Alternative considered: Space Grotesk. It has more character, but its figures are less even in dense tables.

### 9. Removing theme code
- `index.html`: drop the `theme-init.js` script and set `theme-color` to the new `bg`.
- `index.css`: delete `:root[data-theme=…]` blocks; keep `html { color-scheme: dark }`.
- Delete `lib/theme.ts`, `lib/theme.test.ts`, `components/ThemeToggle.tsx`, `ThemeToggle.test.tsx`, `public/theme-init.js`, `theme-init.test.ts`, and `pl.theme`. In `Layout.test.tsx`, delete the "Motyw radiogroup" test.
- `theme-contrast.test.ts`: drop the light-counterpart check and the `ThemeToggle` source import; keep the contrast, badge-tone and bucket checks and extend them to `positive`/`negative` on `surface`.

## Risks / Trade-offs

- [Restyling changes markup that tests query by class or structure] → Extract the shared pieces in a separate step from restyling. Tests query by role, text and `data-testid`; keep those stable, and update only tests that relied on removed markup.
- [Darker green and red fail AA on the darker background] → The contrast test is the gate; adjust lightness and record the final values in Decision 6.
- [Dot grid and glow hurt readability or scroll performance] → Keep the opacity ≤ 0.05; `background-attachment: fixed` on `body` only; check the look in the running app (`make dev-web`).
- [`signOf` uses `Number` on a decimal string] → It is used only to compare with zero, never for display or arithmetic, so precision loss cannot show up on screen.
- [Overlap with parked `improve-ui-kit-accessibility`] → That change stays parked; add a note that "both themes" now means the dark theme only. Shared components keep their current ARIA roles so that change can build on them.
- [Font packages add ~100 kB of woff2] → Variable fonts with the latin and latin-ext subsets only (Polish needs latin-ext).
