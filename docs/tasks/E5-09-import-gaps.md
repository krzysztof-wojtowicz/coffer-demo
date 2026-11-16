# E5-09: Import: granice modułów, kategoryzacja z historii, zbiór N05

**Fala:** E5/3 · **Zależności:** E5-01 · **Role:** backend (aragorn) · **UC / wymagania:** UC-02, F05, F07, F08, N05

## Cel
Weryfikacja wykazała, że deduplikacja (F05) i kategoryzacja (F07) działają, ale: `imports/service.py` czyta model `coffer.transactions.models` (naruszenie granic), deduplikacja wczytuje wszystkie transakcje użytkownika, kategoryzator nie uczy się z poprawek użytkownika (F08), a N05 nie ma zbioru testowego. Po karcie wszystkie cztery luki są zamknięte.

## Przeczytaj
- `src/backend/coffer/imports/{service,dedup,categorize,parser}.py`, `src/backend/coffer/transactions/{service,models}.py`
- `docs/csv-format.md`, `data/fixtures/csv/testbank-2026-10.csv`, `src/backend/tests/imports/test_units.py`

## Pliki
- **aragorn:** `src/backend/coffer/imports/{service,dedup,categorize}.py`, `src/backend/coffer/transactions/service.py` (tylko nowe funkcje), `data/fixtures/categorization/n05-200.csv` (nowy, dane wymyślone), testy `src/backend/tests/imports/{test_dedup_range,test_categorize_hints,test_n05}.py`, `tests/transactions/test_hints.py`

## Kontrakt
- `transactions.service.dedup_keys(db, user_id, start: date, end: date) -> Counter[tuple[date, Decimal, str]]` (tylko zakres dat z pliku, klucz z `imports.dedup.dedup_key` przeniesiony do `transactions.service.normalize_description`); `imports/service.py` nie importuje `coffer.transactions.models`.
- Klucz deduplikacji: data, kwota, opis po normalizacji spacji **i `casefold()`** (F05 „ten sam opis” bez wrażliwości na wielkość liter). Identyczne wiersze w jednym pliku nadal importowane (np. dwie kawy) – zachowanie opisane w docstringu.
- `transactions.service.category_hints(db, user_id) -> dict[str, str]`: znormalizowany opis → nazwa kategorii z najnowszej transakcji użytkownika z `needs_review = false`.
- `categorize(description, hints: Mapping[str, str] | None = None) -> str | None`: najpierw dokładne trafienie w `hints`, potem reguły słów kluczowych (rozszerzone o typowe polskie sklepy/usługi), inaczej `None` (wiersz `needs_review`).
- `n05-200.csv`: 200 wymyślonych transakcji w formacie testowego banku z kolumną oczekiwanej kategorii; test: kategoryzator (bez `hints`) trafia ≥ 80% (N05). Zbiór nie może być strojony 1:1 pod reguły – min. 30 opisów spoza słów kluczowych ze zbioru.

## Testy (aragorn)
- Import pliku z marca nie czyta transakcji spoza marca (zapytanie z zakresem; asercja na wywołaniu serwisu lub liczbie wierszy).
- `ALLEGRO` vs `allegro` → duplikat; poprawiona przez użytkownika kategoria opisu „SKLEP U ZOSI” jest proponowana przy następnym imporcie.
- N05 ≥ 80%; wynik procentowy w raporcie.

## Kryteria akceptacji
- [ ] `make lint` (granice modułów); `COFFER_TEST_DB=coffer_test_aragorn make test-backend ARGS="tests/imports tests/transactions"`
- [ ] API importu bez zmian kształtu (brak potrzeby `make openapi`)

## Poza zakresem
Kategoryzacja przez LLM (`anonymize.scrub`), kategorie użytkownika.
