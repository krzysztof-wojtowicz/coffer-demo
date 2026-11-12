# E4-04: Historia majątku w czasie (wykres)

**Fala:** E4/2 · **Zależności:** E4-01 · **Role:** implementer + tester · **UC / wymagania:** F26, UC-11

## Cel
Na stronie Podsumowanie użytkownik widzi wykres środków na kontach w czasie (miesiąc po miesiącu), zgodny z saldem początkowym i transakcjami.

## Przeczytaj
- `CLAUDE.md` (ładuje się automatycznie)
- `src/backend/coffer/analytics/net_worth.py`, `src/backend/coffer/budget/{service,api,schemas}.py`
- `src/frontend/src/features/budget/{SummaryPage,NetWorthCard}.tsx`

## Pliki
- **implementer:** `src/backend/coffer/analytics/net_worth.py` (funkcja szeregu), `src/backend/coffer/budget/{service,api,schemas}.py`, `src/frontend/src/features/budget/NetWorthChart.tsx` (nowy), `queries.ts`, `SummaryPage.tsx`
- **tester:** `src/backend/tests/analytics/`, `tests/budget/`, test frontu wykresu

## Kontrakt
- `GET /api/budget/net-worth/history?months=12` (1–60, domyślnie 12) → `{points: [{month: "YYYY-MM", cash_balance: "0.00"}]}`; saldo na koniec miesiąca (dla bieżącego: na dziś) = saldo początkowe + suma transakcji do tej daty.
- Seria tylko dla środków na kontach: wartość portfela w przeszłości nie jest przechowywana (poza zakresem). Kwoty jako stringi, suma w `coffer.analytics` (czysta funkcja).
- UI: lekki wykres liniowy SVG (bez nowej ciężkiej zależności, chyba że zespół zdecyduje inaczej), opisy po polsku, tabela alternatywna dla czytników ekranu.

## Kryteria akceptacji
- [ ] `make lint`, testy testera, `make check-web`, `make openapi`
- [ ] ostatni punkt serii = `cash_balance` z `GET /api/budget/net-worth`
- [ ] test `hypothesis`: seria jest spójna z sumą transakcji

## Poza zakresem
Historia wartości portfela, prognozy.
