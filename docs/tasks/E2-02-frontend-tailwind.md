# E2-02: Frontend: Tailwind CSS, komponenty UI, wybór miesiąca

**Fala:** E2/1 · **Zależności:** E1-06 · **Role:** implementer + tester · **UC / wymagania:** UC-09, UC-10, UC-11, N06

## Cel
Cały frontend używa Tailwind CSS i wspólnych komponentów. Wybór miesiąca to wygodny picker zamiast pola tekstowego (`<input type="month">` w Safari i Firefoksie wyświetla się jako zwykły tekst).

## Przeczytaj
- `src/frontend/src/` (cały, to mały kod), `src/frontend/vite.config.ts`, `src/frontend/package.json`

## Pliki
- **implementer:** `src/frontend/**` poza `src/features/assistant/` (panel asystenta przebuduje E2-05) i poza plikami testów `*.test.tsx` w `src/components/`
- **tester:** `src/frontend/src/components/MonthPicker.test.tsx`, `src/frontend/src/components/ui/*.test.tsx`

## Kontrakt
- **Tailwind v4** przez `@tailwindcss/vite`; `src/index.css` zawiera tylko `@import "tailwindcss";` i ewentualnie `@theme` z kolorami marki (spokojny zielono-granatowy motyw finansowy). Usuń dotychczasowe klasy CSS. Bez innych bibliotek UI.
- Dodaj zależności dev: `@testing-library/react`, `@testing-library/user-event`, `jsdom`; w `vite.config.ts` `test: { environment: "jsdom" }`.
- `src/components/ui/`: `Button` (warianty `primary | secondary | ghost | danger`, `size sm | md`, prop `loading` pokazuje spinner i blokuje kliknięcie), `Card` (`title?`, `actions?`, `children`), `Badge` (`tone: neutral | success | warning | danger | info`), `Spinner`, `Field` (etykieta + błąd pod polem), `Select`, `Input`. Każdy z `className` do rozszerzenia.
- `src/components/MonthPicker.tsx`: `MonthPicker({ value: string /* "YYYY-MM" */, onChange(value: string): void, max?: string })`.
  - Widok: `‹` | przycisk z nazwą „październik 2026” | `›`. Strzałki zmieniają miesiąc o 1; `›` wyłączona, gdy następny miesiąc > `max`.
  - Kliknięcie nazwy otwiera popover: nagłówek z rokiem i strzałkami roku, siatka 3×4 skróconych nazw miesięcy (sty, lut, …, gru). Bieżąca wartość wyróżniona, miesiące > `max` wyłączone. Wybór zamyka popover; `Escape` i kliknięcie poza nim też zamykają.
  - Nazwy z `Intl.DateTimeFormat("pl-PL", { month: "long" })` (mianownik: użyj `month: "long"` z `day` pominiętym, sprawdź, że daje „październik”, a nie „października”; w razie problemu stała lista polskich nazw w `pl.ts`).
  - Dostępność: przyciski z `aria-label` („Poprzedni miesiąc”, „Następny miesiąc”, „Wybierz miesiąc”), popover z `role="dialog"`, miesiące jako przyciski z `aria-pressed` dla wybranego.
- Użyj `MonthPicker` w podsumowaniu i w filtrze transakcji (`max` = bieżący miesiąc).
- `Layout`: górny pasek z logo „Coffer”, nawigacja (Podsumowanie, Transakcje, Import: link do `/import`, strona powstanie w E2-03; do tego czasu prosta strona-zaślepka), e-mail użytkownika i „Wyloguj”. Responsywnie (na wąskim ekranie nawigacja zawija się).
- Podsumowanie: kafelki kwot w `Card`, wydatki per kategoria jako lista z poziomym paskiem udziału (szerokość paska = `expenses / total` liczona tylko do stylu, wartości wyświetlane wyłącznie ze stringów z API).
- Transakcje: formularz w `Card` obok/nad listą; lista jako tabela, kwoty wyrównane do prawej, wydatki czerwone, przychody zielone; `Badge` dla `source` („ręczna”/„import”).
- Panel asystenta zostaw działający (tylko owinięty w `Card`), przebudowa w E2-05.

### Testy (tester, vitest + Testing Library, bez czytania implementacji poza propsami z tej karty)
- `MonthPicker`: wyświetla polską nazwę; `‹`/`›` wołają `onChange` z poprzednim/następnym miesiącem (granica roku gru↔sty); `›` wyłączona przy `max`; popover otwiera się, wybór miesiąca woła `onChange` i zamyka; `Escape` zamyka; zmiana roku w popoverze.
- `Button`: `loading` blokuje `onClick`.

## Kryteria akceptacji
- [ ] `make check-web` przechodzi (z testami testera)
- [ ] brak klas z dawnego `index.css`, brak plików CSS poza `index.css`
- [ ] wszystkie teksty po polsku w `src/i18n/pl.ts`
