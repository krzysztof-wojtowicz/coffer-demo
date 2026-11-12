# E4-02: Filtrowanie i paginacja transakcji po stronie serwera

**Fala:** E4/1 · **Zależności:** — · **Role:** implementer + tester · **UC / wymagania:** UC-03, F06

## Cel
Lista transakcji przestaje być ograniczona do jednego miesiąca: filtry (zakres dat, typ, kategoria, źródło, tekst) i sortowanie działają na serwerze, a lista jest stronicowana.

## Przeczytaj
- `CLAUDE.md` (ładuje się automatycznie)
- `src/backend/coffer/transactions/{api,service,schemas}.py`
- `src/frontend/src/features/transactions/{TransactionsPage.tsx,list.ts,queries.ts}`

## Pliki
- **implementer:** `src/backend/coffer/transactions/{api,service,schemas}.py`, `src/frontend/src/features/transactions/{TransactionsPage.tsx,list.ts,queries.ts}`
- **tester:** `src/backend/tests/transactions/`, `src/frontend/src/features/transactions/list.test.ts`

## Kontrakt
- `GET /api/transactions?date_from&date_to&type=income|expense&category_id&source=manual|import&q&sort=date|amount&order=asc|desc&limit&offset` → `{items: TransactionOut[], total: int}` (limit domyślnie 50, max 200). Parametr `month` zostaje (kompatybilność), a `date_from > date_to` → 422 „Nieprawidłowy zakres dat”.
- Wszystkie zapytania filtrują po `user_id`; sortowanie stabilne (drugi klucz `id`).
- Wynik zmienia kształt odpowiedzi (lista → obiekt): frontend i `make openapi` w tej samej karcie.
- UI: filtry wysyłane do API, zakres dat zamiast samego miesiąca, przycisk „Pokaż więcej” lub paginacja.

## Kryteria akceptacji
- [ ] `make lint`, testy testera, `make check-web`, `make openapi`
- [ ] test: cudze transakcje nigdy nie trafiają do wyniku ani do `total`
- [ ] test sortowania i granic stron (offset poza końcem → pusta lista)

## Poza zakresem
Eksport CSV (F09), zapisywanie filtrów.
