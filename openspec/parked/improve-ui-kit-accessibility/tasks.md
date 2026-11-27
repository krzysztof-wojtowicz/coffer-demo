## 1. Implementer
- [ ] 1.1 `Select`: combobox/listbox ARIA and keyboard support
- [ ] 1.2 `DatePicker`: grid role and keyboard navigation, Polish labels
- [ ] 1.3 `ConfirmDialog`: alertdialog role, focus trap, focus return, Esc
- [ ] 1.4 Popover: Esc, outside click, focus return
- [ ] 1.5 `ThemeToggle` and icon buttons: Polish `aria-label`; visible `focus-visible` in both themes

## 2. Tester
- [ ] 2.1 user-event keyboard tests for each of the 4 components
- [ ] 2.2 AA contrast check in `theme-contrast.tester.test.ts`

## 3. Verify
- [ ] 3.1 `make check-web` passes
- [ ] 3.2 `grep -rn "<div onClick" src/frontend/src` finds nothing
