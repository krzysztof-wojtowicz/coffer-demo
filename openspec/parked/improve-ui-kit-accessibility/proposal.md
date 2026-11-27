## Why
The custom UI components (`Select`, `DatePicker`, `ConfirmDialog`, the portal popover, the theme toggle, inline edit) are not fully usable with a keyboard or a screen reader.

## What Changes
- `Select`: the combobox/listbox pattern with arrows, Home/End, Enter/Space, Esc and first-letter search.
- `DatePicker`: a `role="grid"` day grid with arrow and PageUp/PageDown navigation and Polish date labels.
- `ConfirmDialog`: `role="alertdialog"`, a focus trap, focus returned to the trigger, and Esc to close.
- Portal popover: closes on Esc and on an outside click, and returns focus.
- Icon buttons get Polish `aria-label`s, focus is visible in both themes, and text contrast meets AA.
- Component public APIs stay the same (drop-in).

## Capabilities
### New Capabilities
- `ui-accessibility`: keyboard and screen-reader support of the UI kit.

## Impact
- `src/frontend/src/components/ui/**`, `src/frontend/src/components/ThemeToggle.tsx` (`Layout.tsx` layout unchanged)
- Tests next to components (`*.test.tsx`) and `theme-contrast.tester.test.ts`

## Out of scope
A full WCAG audit of the app and testing with real screen readers on devices.

> **Note (2026-11-27):** the `ui-refactor` change removes the light theme and `ThemeToggle`. When resuming, read "both themes" as the dark theme only and drop the theme-toggle items.
