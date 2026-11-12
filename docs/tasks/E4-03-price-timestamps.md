# E4-03: Data aktualizacji cen w portfelu

**Fala:** E4/1 · **Zależności:** — · **Role:** implementer + tester · **UC / wymagania:** UC-04, F22, F25

## Cel
Użytkownik widzi, z jakiej chwili pochodzą notowania i kursy użyte do wyceny portfela, oraz które pozycje mają cenę nieaktualną.

## Przeczytaj
- `CLAUDE.md` (ładuje się automatycznie)
- `src/backend/coffer/market/service.py` (`Quote.as_of`), `src/backend/coffer/portfolio/{service,schemas,api}.py`
- `src/frontend/src/features/portfolio/PortfolioPage.tsx`, `src/frontend/src/features/budget/PortfolioSummaryCard.tsx`

## Pliki
- **implementer:** `src/backend/coffer/portfolio/{service,schemas,api}.py`, `src/frontend/src/features/portfolio/`, `src/frontend/src/features/budget/PortfolioSummaryCard.tsx`
- **tester:** `src/backend/tests/portfolio/`, testy frontu portfela

## Kontrakt
- `GET /api/portfolio/summary` dodaje `prices_as_of: datetime | null` (najstarszy `as_of` spośród użytych notowań i kursów; `null`, gdy żadnych) oraz `as_of: datetime | null` w pozycji z notowania rynkowego.
- Bez zmian zasad wyceny i `value_source`; sumy nadal liczy `coffer.analytics`.
- UI: „Ceny z: <data i godzina>” na stronie portfela i karcie portfela; pozycje bez notowania oznaczone jak dziś, z dodatkową informacją o wieku ceny, gdy starsza niż 24 h.

## Kryteria akceptacji
- [ ] `make lint`, testy testera, `make check-web`, `make openapi`
- [ ] test z mockiem rynku (bez sieci): znaczniki czasu w odpowiedzi, `null` bez notowań

## Poza zakresem
Job okresowej aktualizacji cen (F25), historia cen.
