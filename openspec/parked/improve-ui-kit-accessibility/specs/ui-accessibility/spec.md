## ADDED Requirements

### Requirement: Keyboard-operable UI kit
`Select`, `DatePicker`, `ConfirmDialog` and the portal popover SHALL be fully operable with a keyboard and SHALL expose the matching ARIA roles and states (combobox/listbox, grid, alertdialog), without changing their public props.

#### Scenario: Select with the keyboard
- **WHEN** a focused `Select` receives arrow keys, Home/End, Enter/Space, Esc or a letter
- **THEN** the active option moves, is chosen, the list closes, or jumps to the first option with that letter, and `aria-activedescendant` follows

#### Scenario: Dialog focus
- **WHEN** a `ConfirmDialog` opens and later closes
- **THEN** focus stays inside it while open, Esc closes it, and focus returns to the trigger

### Requirement: Accessible names and focus
Icon-only buttons SHALL have Polish `aria-label`s, keyboard focus SHALL be visible in both themes, and text SHALL meet WCAG AA contrast. No clickable `div` SHALL be used in place of a button.

#### Scenario: Theme toggle
- **WHEN** a screen reader reaches the theme toggle
- **THEN** it announces a Polish label describing the action
