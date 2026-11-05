# E3-04: Frontend: ciemny motyw z zielonym akcentem

**Fala:** E3/1 · **Zależności:** E2 · **Role:** implementer · **Wymagania:** N06

## Cel
Cała aplikacja w ciemnym motywie; zielony jako kolor akcentu (pieniądze). Czytelne kontrasty (WCAG AA dla tekstu).

## Przeczytaj
- `src/frontend/src/index.css`, `src/frontend/src/components/**`, `src/frontend/index.html`
- pozostałe pliki `src/frontend/src/features/**` tylko w zakresie klas Tailwind (szukaj `grep -rn "className"`)

## Pliki
- **implementer:** `src/frontend/**` (poza `api/schema.d.ts`). Nie zmieniaj logiki: wylogowanie (`features/auth/queries.ts`, `lib/queryClient.ts`, `api/client.ts`) zostało właśnie poprawione.

## Kontrakt
- Tokeny w `@theme` w `index.css`, nazwane semantycznie i używane w całym kodzie zamiast surowych kolorów (`bg-surface`, `text-muted`, `border-border` itd.):
  - `bg` `#0b0f14` (tło strony), `surface` `#121821` (karty), `surface-2` `#1a2230` (pola, wiersze hover), `border` `#253041`,
  - `text` `#e6e9ef`, `muted` `#94a0b4`,
  - `accent` `#22c55e` (zielony: przyciski główne, aktywna nawigacja, focus), `accent-strong` `#16a34a` (hover), `accent-soft` (zielony z przezroczystością na tła wyróżnień),
  - `positive` `#4ade80` (przychody, nadwyżka), `negative` `#f87171` (wydatki, deficyt), `warning` `#fbbf24`, `info` `#60a5fa`.
- `html { color-scheme: dark; }`, żeby natywne kontrolki (select, checkbox, date, scrollbar) były ciemne; `<meta name="theme-color" content="#0b0f14">`.
- Wszystkie komponenty `ui/` (Button: `primary` zielony z ciemnym tekstem; `secondary` `surface-2` z obramowaniem; `danger` czerwony; `ghost`), `Card`, `Badge` (tony na ciemnym tle: przyciemnione tło + jasny tekst), `Input`/`Select` (tło `surface-2`, focus ring `accent`), `MonthPicker` (popover na `surface`, wybrany miesiąc `accent`), `Layout`, tabele, paski udziału (wypełnienie `accent`), panel asystenta, strona importu, logowanie.
- Brak białych teł i szarych tekstów o niskim kontraście. Brak przełącznika motywów (tylko ciemny).

## Kryteria akceptacji
- [ ] `make check-web` przechodzi (istniejące testy bez zmian)
- [ ] `grep -rnE "bg-white|text-gray-[5-9]00|bg-gray-(50|100)" src/frontend/src` nic nie znajduje
