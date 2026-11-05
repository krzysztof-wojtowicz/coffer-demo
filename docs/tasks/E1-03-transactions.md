# E1-03: Transakcje: ręczne dodanie, lista, usunięcie, kategorie

**Fala:** 1 · **Zależności:** E1-01 · **Role:** implementer + tester · **UC / wymagania:** UC-10, UC-03 (tylko usunięcie), F02, F03, F06 (częściowo), N04

## Cel
Zalogowany użytkownik dodaje transakcję ręcznie, widzi listę swoich transakcji (opcjonalnie z jednego miesiąca) i może je usuwać. Moduł udostępnia `list_views` dla budżetu.

## Przeczytaj
- `docs/use-cases/UC-10-add-transaction.md`
- `src/backend/coffer/transactions/models.py`, `src/backend/coffer/core/{money,months}.py`, `src/backend/coffer/accounts/deps.py` (gotowe, nie zmieniaj)
- `src/backend/tests/conftest.py`
- sekcja „Typy wejściowe” w `docs/tasks/E1-04-budget-analytics.md` (definicja `TxView`)

## Pliki
- **implementer:** `src/backend/coffer/transactions/{api,service,schemas}.py`
- **tester:** `src/backend/tests/transactions/`

## Kontrakt

### Schematy
- `CategoryOut { id: int, name: str, in_budget: bool, is_default: bool }`
- `TransactionCreate { date: date, amount: Decimal, description: str, category_id: int | None = None }`
  - `amount`: ≠ 0, maks. 2 miejsca po przecinku, `|amount| < 1 000 000 000` (inaczej 422). W JSON przyjmowany jako string lub liczba.
  - `description`: obcięty ze spacji, 1–500 znaków.
- `TransactionOut { id, date, amount: Decimal, currency: str, description, category_id, category_name: str, source: str }`; `amount` serializuje się jako string z 2 miejscami (np. `"-45.50"`).

### Endpointy (router z prefiksem `/api`, wszystkie wymagają `CurrentUser`)
| Metoda i ścieżka | Sukces | Błędy |
|---|---|---|
| `GET /categories` | 200 `list[CategoryOut]` posortowane po `name` | 401 |
| `POST /transactions` | 201 `TransactionOut`; brak `category_id` → kategoria z `is_default=True` („Inne”); `currency="PLN"`, `base_amount = amount`, `source="manual"` | 422 walidacja; 422 `{"detail": "Nieznana kategoria"}` |
| `GET /transactions?month=YYYY-MM` | 200 `list[TransactionOut]` tylko użytkownika, sortowane `date` malejąco, potem `id` malejąco; bez `month` → wszystkie | 422 zły format miesiąca |
| `DELETE /transactions/{id}` | 204 | 404 `{"detail": "Nie znaleziono transakcji"}` także dla cudzej transakcji |

### Serwis (`service.py`)
- `list_categories(db) -> list[Category]`
- `create(db, user_id: int, data: TransactionCreate) -> Transaction`
- `list_for_user(db, user_id: int, month: str | None) -> list[Transaction]`
- `delete(db, user_id: int, transaction_id: int) -> bool`
- **`list_views(db, user_id: int, start: date, end: date) -> list[TxView]`**: transakcje użytkownika z `start <= date < end` jako `coffer.analytics.month.TxView` (`base_amount`, kategoria, `in_budget`). Kontrakt dla E1-04; `TxView` importuj z `coffer.analytics.month` (jeśli plik jeszcze nie istnieje, bo E1-04 pracuje równolegle, poczekaj na niego przed uruchomieniem testów albo zgłoś w raporcie).

## Kryteria akceptacji
- [ ] `make lint` przechodzi
- [ ] testy testera przechodzą, w tym: izolacja użytkowników (lista i usuwanie), kategoria domyślna, kwoty z groszami bez utraty precyzji (`"0.10"` + `"0.20"` zapisane i odczytane dokładnie), odrzucenie `"1.005"` i `0`

## Poza zakresem
Edycja transakcji i zmiana kategorii (Etap 2), import CSV (Etap 2), waluty obce, ostrzeżenie o duplikacie.
