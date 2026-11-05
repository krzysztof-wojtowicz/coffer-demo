# E2-01: Import CSV: podgląd, deduplikacja, kategoryzacja regułami, zatwierdzenie

**Fala:** E2/1 · **Zależności:** E1 · **Role:** implementer + tester · **UC / wymagania:** UC-02, F04, F05, F07 (reguły), F08, N04

## Cel
Użytkownik wgrywa plik CSV w formacie testowym, widzi podgląd z kategoriami i duplikatami, poprawia kategorie, wybiera wiersze i zatwierdza import.

## Przeczytaj
- `docs/use-cases/UC-02-import-transactions.md`, `docs/csv-format.md`, `data/fixtures/csv/testbank-2026-10.csv`
- `src/backend/coffer/transactions/{models,schemas}.py`, `src/backend/coffer/core/money.py`
- `src/backend/tests/conftest.py`
- jako wzór migracji: `src/backend/alembic/versions/0001_initial.py` (tylko nagłówek)

## Pliki
- **implementer:** `src/backend/coffer/imports/{__init__,api,service,schemas,models,parser,dedup,categorize,banks}.py`, `src/backend/alembic/versions/0002_import_drafts.py`, `src/backend/coffer/main.py` (dopięcie routera), `src/backend/pyproject.toml` (zależność `python-multipart`; kontrakt import-linter: dopisz `coffer.imports` do listy modułów rdzenia), w `src/backend/tests/conftest.py` **tylko** dopisanie `import_drafts` do `TRUNCATE`
- **tester:** `src/backend/tests/imports/`

## Kontrakt

### Moduł `coffer.imports`
Nowy moduł rdzenia. Zapisuje transakcje przez model `Transaction` (zgodnie z zasadą modułów: tworzenie przez `transactions.service`, jeśli wystarcza; w razie potrzeby dodaj tam funkcję `bulk_create` i opisz to w raporcie).

- `banks.py`: konfiguracja jako dane (dataclass `BankConfig`), na razie jeden bank `testbank` z wartościami z `docs/csv-format.md`. `BANKS: dict[str, BankConfig]`.
- `parser.py`: `parse(content: bytes, bank: BankConfig) -> list[ParsedRow]`, gdzie `ParsedRow(index, date | None, amount: Decimal | None, currency | None, description, error: str | None)`. Kwota `"-1 234,56"` → `Decimal("-1234.56")` (obsłuż też twardą spację U+00A0). Błędny wiersz nie przerywa parsowania, tylko dostaje `error` po polsku. Brak wymaganych kolumn w nagłówku → `ImportFormatError` („Plik nie pasuje do formatu banku: brak kolumny „Opis””).
- `categorize.py`: `categorize(description: str) -> str | None` zwraca nazwę kategorii według listy reguł „słowo kluczowe w opisie (bez rozróżniania wielkości liter) → kategoria”, np. BIEDRONKA/LIDL/ŻABKA/AUCHAN → Jedzenie; MPK/ORLEN/PKP/UBER/BOLT → Transport; CZYNSZ → Mieszkanie; PRĄD/TAURON/GAZ/INTERNET → Rachunki; APTEKA → Zdrowie; NETFLIX/SPOTIFY/KINO → Rozrywka; ALLEGRO/ZALANDO → Zakupy; WYNAGRODZENIE → Wynagrodzenie; PRZELEW WŁASNY → Przelewy własne; DOM MAKLERSKI → Inwestycje. Pierwsza pasująca reguła wygrywa; brak → `None` (kategoria „Inne” z `needs_review=True`).
- `dedup.py`: `mark_duplicates(rows, existing: Counter[tuple[date, Decimal, str]]) -> set[int]` zwraca indeksy duplikatów. **Multizbiór:** klucz = (data, kwota, opis po `" ".join(opis.split())`); jeśli plik ma k wierszy z kluczem, a baza n, to pierwsze `min(k, n)` wystąpień w pliku to duplikaty.
- Kwota niebędąca liczbą skończoną albo `|kwota| ≥ 1 000 000 000` → wiersz `error` „Kwota poza zakresem” (ta sama granica co przy ręcznym dodaniu; kolumna `NUMERIC(14,2)`). Dodane po przeglądzie.
- Waluta inna niż PLN → wiersz ze statusem `error`: „Waluta EUR nie jest jeszcze obsługiwana (kursy NBP w kolejnym etapie)”.

### Model i migracja `0002`
`ImportDraft` (tabela `import_drafts`): `id` str(36) PK (uuid4), `user_id` FK users CASCADE, `bank` str, `filename` str(255), `rows` JSONB, `created_at`, `expires_at` (+1 h).

### Endpointy (prefiks `/api/imports`, wszystkie z `CurrentUser`)
| Metoda i ścieżka | Wejście | Sukces | Błędy |
|---|---|---|---|
| `GET /banks` | — | 200 `[{id, name}]` | — |
| `POST ""` | multipart: `file`, `bank` (form) | 201 `ImportPreviewOut` | 422 „Nieobsługiwany bank”; 422 „Plik jest za duży (maks. 1 MB)”; 422 „Plik nie zawiera transakcji”; 422 z `ImportFormatError`; 422 „Nie udało się odczytać pliku (kodowanie)” |
| `GET /{id}` | — | 200 `ImportPreviewOut` | 404 „Nie znaleziono podglądu importu” (także cudzy lub wygasły) |
| `POST /{id}/commit` | `CommitIn` | 200 `CommitOut`, podgląd usunięty | 404 jw.; 422 „Nieznana kategoria” |
| `DELETE /{id}` | — | 204 | 404 jw. |

Schematy:
```
ImportRowOut { index: int, date: date | None, amount: Decimal | None, currency: str | None,
               description: str, category_id: int | None, needs_review: bool,
               status: "new" | "duplicate" | "error", error: str | None }
ImportPreviewOut { id: str, bank: str, filename: str, expires_at: datetime,
                   rows: list[ImportRowOut], counts: { new: int, duplicate: int, error: int } }
CommitIn  { rows: list[{ index: int, include: bool, category_id: int | None }] = [] }
CommitOut { imported: int, skipped_duplicates: int, skipped_errors: int }
```
Reguły zatwierdzenia:
- domyślnie importowane są wiersze `new`; `CommitIn.rows` nadpisuje `include` i `category_id` dla wskazanych indeksów; wiersze `error` nigdy nie są importowane; `duplicate` tylko z `include=true` (świadoma decyzja użytkownika),
- **ponowna deduplikacja** względem bazy w chwili zatwierdzenia (dane mogły się zmienić),
- wszystko w jednej transakcji DB; `source="import"`, `currency="PLN"`, `base_amount=amount`; `needs_review=False`, jeśli użytkownik jawnie podał kategorię, w przeciwnym razie wartość z podglądu.

## Kryteria akceptacji
- [ ] `make lint` przechodzi
- [ ] testy testera przechodzą, w tym na pliku `data/fixtures/csv/testbank-2026-10.csv`: 17 wierszy `new`, 1 `error` (EUR); ponowny import po zatwierdzeniu → same duplikaty; dwa identyczne bilety MPK: w bazie 1, w pliku 2 → 1 `new` i 1 `duplicate`
- [ ] izolacja użytkowników (cudzy podgląd → 404), wygasły podgląd → 404

## Poza zakresem
Inne banki, kursy NBP, uczenie reguł z poprawek, anonimizacja (brak AI w imporcie).
