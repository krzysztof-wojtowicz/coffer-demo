# E4-06: Dostępność (a11y) nowych komponentów UI

**Fala:** E4/1 · **Zależności:** — · **Role:** implementer + tester · **UC / wymagania:** N06

## Cel
Własne komponenty (`Select`, `DatePicker`, `ConfirmDialog`, popover w portalu, przełącznik motywu, edycja inline) są w pełni obsługiwalne klawiaturą i czytnikiem ekranu.

## Przeczytaj
- `CLAUDE.md` (ładuje się automatycznie)
- `src/frontend/src/components/ui/{Select,DatePicker,ConfirmDialog,popover}.tsx` i ich testy
- `src/frontend/src/components/{Layout,ThemeToggle}.tsx`, `src/frontend/src/features/transactions/TransactionRow.tsx`

## Pliki
- **implementer:** `src/frontend/src/components/ui/**`, `src/frontend/src/components/ThemeToggle.tsx` (bez zmian układu `Layout.tsx`; potrzebna zmiana tam → raport)
- **tester:** testy obok komponentów (`*.test.tsx`), kontrast w `theme-contrast.tester.test.ts`

## Kontrakt
- `Select`: wzorzec `combobox`/`listbox` (`aria-expanded`, `aria-controls`, `aria-activedescendant`), strzałki, Home/End, Enter/Space, Esc, wyszukiwanie po pierwszej literze.
- `DatePicker`: siatka dni z `role="grid"`, nawigacja strzałkami i PageUp/PageDown, etykiety dat po polsku.
- `ConfirmDialog`: `role="alertdialog"`, pułapka fokusu, powrót fokusu do wyzwalacza, Esc zamyka.
- Popover w portalu: zamykanie Esc i kliknięciem poza, fokus wraca do wyzwalacza.
- Przyciski ikonowe (motyw, Edytuj) mają `aria-label` po polsku; widoczny `focus-visible` w obu motywach; kontrast tekstu AA.
- Bez zmiany publicznego API komponentów (drop-in).

## Kryteria akceptacji
- [ ] `make check-web` przechodzi
- [ ] testy klawiatury dla każdego z 4 komponentów (user-event)
- [ ] `grep -rn "<div onClick" src/frontend/src` nic nie znajduje

## Poza zakresem
Pełny audyt WCAG całej aplikacji, testy czytnikami ekranu na prawdziwych urządzeniach.
