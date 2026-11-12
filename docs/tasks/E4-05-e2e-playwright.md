# E4-05: Testy e2e kluczowych przepływów (Playwright)

**Fala:** E4/3 · **Zależności:** E4-01, E4-02 (stabilny UI) · **Role:** tester · **UC / wymagania:** UC-01, UC-02, UC-03, UC-04, UC-10, UC-12

## Cel
Automatyczne testy przeglądarkowe sprawdzają najważniejsze przepływy na prawdziwym backendzie (baza testowa, `COFFER_LLM_PROVIDER=none` lub `FakeLLM`), bez sieci zewnętrznej.

## Przeczytaj
- `CLAUDE.md` (ładuje się automatycznie)
- `Makefile`, `docs/deploy/ci.md`, `.github/workflows/ci.yml`
- `src/frontend/package.json`, `docs/csv-format.md`, `data/fixtures/`

## Pliki
- **tester:** `src/frontend/e2e/**`, `src/frontend/playwright.config.ts`, `src/frontend/package.json` (skrypt `e2e`, zależność dev), `Makefile` (cel `e2e`), job w `.github/workflows/ci.yml` (jeśli właściciel CI się zgodzi)

## Kontrakt
Scenariusze (każdy w osobnym użytkowniku, unikalny e-mail):
- rejestracja → dodanie transakcji (panel) → edycja inline → usunięcie przez modal → podsumowanie zgadza się co do grosza;
- import CSV z `data/fixtures/` (podgląd → zatwierdzenie → ponowny import daje duplikaty);
- filtry i sortowanie listy transakcji;
- portfel: dodanie pozycji ręcznej, karta „Majątek” pokazuje wartość netto;
- Doradca AI z wyłączonym modelem: komunikat o niedostępności, reszta aplikacji działa;
- wylogowanie i przekierowanie z `/import` i `/profile`.
Testy nie łączą się z yfinance ani LLM.

## Kryteria akceptacji
- [ ] `make e2e` przechodzi lokalnie na czystej bazie testowej (`COFFER_TEST_DB=coffer_test_<imię>`)
- [ ] testy nie zostawiają danych poza własnymi użytkownikami
- [ ] czas całego zestawu < 3 min

## Poza zakresem
Testy wizualne (screenshoty), testy na produkcji, wiele przeglądarek.
