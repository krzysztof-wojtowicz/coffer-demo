# E2-03: Frontend: strona importu CSV

**Fala:** E2/2 · **Zależności:** E2-01, E2-02 · **Role:** implementer · **UC / wymagania:** UC-02, F04, F05, F08, N06

## Cel
Na stronie `/import` użytkownik wgrywa plik, przegląda podgląd, poprawia kategorie, wybiera wiersze i zatwierdza import.

## Przeczytaj
- `docs/use-cases/UC-02-import-transactions.md`
- sekcja „Kontrakt” w `docs/tasks/E2-01-csv-import.md`
- `src/frontend/src/components/ui/*.tsx` (tylko propsy), `src/frontend/src/features/transactions/queries.ts`, `src/frontend/src/api/client.ts`, `src/frontend/src/i18n/pl.ts`, `src/frontend/src/App.tsx`
- typy: `grep -n "imports" src/frontend/src/api/schema.d.ts`

## Pliki
- **implementer:** `src/frontend/src/features/import/**`, `src/frontend/src/App.tsx` (trasa `/import` zamiast zaślepki), `src/frontend/src/i18n/pl.ts` (tylko nowa sekcja `import`)

## Kontrakt
- **Krok 1, wybór pliku:** `Select` banku z `GET /api/imports/banks` (domyślnie pierwszy), strefa „przeciągnij plik CSV lub kliknij, aby wybrać” (drag & drop + ukryty `<input type="file" accept=".csv,text/csv">`), nazwa i rozmiar wybranego pliku, przycisk „Wczytaj podgląd” (`loading` w trakcie). Upload przez `fetch` z `FormData` (openapi-fetch słabo obsługuje multipart; typ odpowiedzi nadal z `schema.d.ts`). Błędy 422 pokazane nad strefą.
- **Krok 2, podgląd:** podsumowanie jako `Badge`: „N nowych”, „N duplikatów”, „N błędów”. Tabela: checkbox „importuj” (domyślnie zaznaczone tylko `new`; `error` zablokowane), data, opis, kwota (kolory jak na liście transakcji), `Select` kategorii (domyślnie z podglądu; `null` → „Inne”), `Badge` statusu (nowa / duplikat / błąd z treścią `error` w `title`) i znacznik „do sprawdzenia” przy `needs_review`. Filtr: wszystkie / tylko nowe / duplikaty / błędy. Przycisk główny „Importuj N transakcji” (N = liczba zaznaczonych) i „Anuluj” (`DELETE`, powrót do kroku 1).
- Zatwierdzenie: `POST /{id}/commit` wysyła **tylko zmienione** wiersze (`include` lub `category_id` inne niż domyślne).
- **Krok 3, wynik:** komunikat sukcesu z `CommitOut` („Zaimportowano 17 transakcji, pominięto 1 duplikat i 1 błąd”, z poprawną polską odmianą przez `Intl.PluralRules("pl-PL")`), przyciski „Zobacz transakcje” i „Importuj kolejny plik”. Po sukcesie unieważnij zapytania transakcji i podsumowania.
- Podgląd wygasł (404) → komunikat i powrót do kroku 1.
- Frontend nie liczy kwot; liczy tylko liczbę zaznaczonych wierszy.

## Kryteria akceptacji
- [ ] `make check-web` przechodzi
- [ ] test vitest dla funkcji odmiany komunikatu wyniku (1, 2, 5, 22 transakcje)
- [ ] ręcznie: import `data/fixtures/csv/testbank-2026-10.csv` → 17 nowych, 1 błąd; ponowny import → 17 duplikatów
