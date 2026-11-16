# E5-08: Front: porównania miesięcy, limity kategorii, data cen, „Oceń zakup”

**Fala:** E5/3 · **Zależności:** E5-02, E5-04, E5-06 · **Role:** frontend (legolas) · **UC / wymagania:** UC-04, UC-07 (1a), UC-11, F12–F15, F22, F25; zastępuje front karty E4-03

## Cel
Na Podsumowaniu użytkownik widzi porównanie wydatków z poprzednim miesiącem, top 3 wzrostów i wykorzystanie limitów (z oznaczeniem przekroczeń) oraz zarządza limitami. W portfelu widzi datę cen i może jednym kliknięciem ocenić wpływ zakupu w asystencie.

## Przeczytaj
- `docs/tasks/E5-02-budget-insights-limits.md` (sekcja Kontrakt), `docs/tasks/E4-03-price-timestamps.md` (sekcja Kontrakt, UI)
- `src/frontend/src/features/budget/{SummaryPage,SummaryTiles,PortfolioSummaryCard,queries}.tsx|ts`, `src/frontend/src/features/portfolio/{PortfolioPage,queries}.tsx|ts`
- `src/frontend/src/features/transactions/queries.ts` (kategorie), `src/frontend/src/components/ui/*`

## Pliki
- **legolas:** `src/frontend/src/features/budget/{InsightsCard,LimitsSection,SummaryPage,PortfolioSummaryCard,queries}.tsx|ts` (+ testy `InsightsCard.test.tsx`, `LimitsSection.test.tsx`), `src/frontend/src/features/portfolio/{PortfolioPage,queries}.tsx|ts` (+ `PortfolioPage.test.tsx`), `src/frontend/src/i18n/pl.ts`, `api/schema.d.ts` + `openapi.json` (`make openapi` na starcie)

## Kontrakt
- **InsightsCard** (dla miesiąca z `MonthPicker` w sekcji historii): tabela F12 (kategoria, ten miesiąc, poprzedni, zmiana zł, zmiana %, strzałka i kolor: wzrost wydatków = ostrzeżenie), sekcja „Największe wzrosty” (F15, maks. 3, kwota ponad średnią 3 mies.), sekcja „Limity” (pasek wykorzystania z `role="progressbar"` + `aria-valuenow`, przekroczenie: odznaka „Przekroczono o X zł”, F14). Brak danych → komunikaty po polsku.
- **LimitsSection:** lista limitów; dodanie/zmiana (Select tylko kategorii `in_budget`, kwota z przecinkiem), usunięcie przez `ConfirmDialog`; błędy 404/422 z API pokazane po polsku; po zmianie odświeżenie `insights` (`invalidateQueries`).
- **Portfel:** „Ceny z: <data i godzina>” (`prices_as_of`) na stronie portfela i w `PortfolioSummaryCard`; pozycja z ceną starszą niż 24 h oznaczona „cena z <data>”. Przycisk „Oceń wpływ zakupu” (ogólny i przy pozycji z symbolem) → `/assistant?action=purchase_impact&asset_class=…&symbol=…` (deep link z E5-06).

## Testy (legolas, vitest)
- Insights: formatowanie zmian i `null` jako „—”, oznaczenie przekroczenia, puste stany.
- Limity: zapis wysyła `PUT` z kropką dziesiętną, usunięcie po potwierdzeniu, błąd 422 widoczny.
- Portfel: `prices_as_of` wyświetlone, link „Oceń wpływ zakupu” ma poprawne parametry.

## Kryteria akceptacji
- [ ] `make check-web`; `make openapi` bez różnic
- [ ] dostępność: progressbar z etykietą, tabela z nagłówkami, dialog z fokusem

## Poza zakresem
Wykres trendów kategorii, cele oszczędnościowe.
