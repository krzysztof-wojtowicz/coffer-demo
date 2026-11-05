# E1-04: Analytics + budżet: podsumowanie miesiąca

**Fala:** 1 · **Zależności:** E1-01 (do testów API także E1-03) · **Role:** implementer + tester · **UC / wymagania:** UC-11 (F10, F11), N04, N08

## Cel
Czysta funkcja liczy podsumowanie miesiąca (przychody, wydatki, saldo, nadwyżka, wydatki per kategoria) dokładnie co do grosza; endpoint `GET /api/budget/{month}` je zwraca.

## Przeczytaj
- `docs/use-cases/UC-11-monthly-analysis.md` (tylko F10, F11)
- `src/backend/coffer/core/{money,months}.py`, `src/backend/coffer/transactions/models.py`
- `src/backend/tests/conftest.py`
- sygnatura `list_views` w `docs/tasks/E1-03-transactions.md`

## Pliki
- **implementer:** `src/backend/coffer/analytics/month.py`, `src/backend/coffer/budget/{api,service,schemas}.py`
- **tester:** `src/backend/tests/analytics/`, `src/backend/tests/budget/`

## Kontrakt

### Typy wejściowe (`coffer/analytics/month.py`, czyste dataclassy `frozen=True`)
```python
TxView(date: date, base_amount: Decimal, category_id: int, category_name: str, in_budget: bool)
CategoryTotal(category_id: int, category_name: str, expenses: Decimal)
MonthSummary(month: str, income: Decimal, expenses: Decimal, balance: Decimal,
             surplus: Decimal, by_category: list[CategoryTotal])
def month_summary(month: str, txs: Iterable[TxView]) -> MonthSummary
```

### Reguły `month_summary`
- Uwzględnia tylko transakcje z datą w danym miesiącu (`YYYY-MM`) i z `in_budget=True`; resztę pomija.
- `income` = suma dodatnich `base_amount`; `expenses` = wartość bezwzględna sumy ujemnych (liczba ≥ 0).
- `balance = income - expenses` (może być ujemne); `surplus = max(balance, 0)`.
- `by_category`: tylko kategorie z wydatkami, `expenses` ≥ 0 per kategoria, sortowanie malejąco po `expenses`, potem po `category_name`.
- Wszystkie kwoty przez `quantize` (2 miejsca); suma `by_category[].expenses` == `expenses` (N04).
- Bez I/O, bez bazy, bez `float`.

### Budżet
- `budget/service.py`: `month_summary(db, user_id: int, month: str) -> MonthSummary` (pobiera `transactions.service.list_views` dla zakresu z `parse_month`, liczy przez `analytics`). Ta funkcja to kontrakt dla E1-05.
- `budget/schemas.py`: `CategoryTotalOut`, `MonthSummaryOut` (te same pola; kwoty jako stringi z 2 miejscami).
- `GET /api/budget/{month}` (`CurrentUser`): 200 `MonthSummaryOut`; zły format miesiąca → 422. Miesiąc bez transakcji → same zera (`"0.00"`) i pusta `by_category`.

### Testy
- `tests/analytics/`: czyste funkcje; przypadki graniczne (pusty miesiąc, tylko wydatki, deficyt, transakcje spoza miesiąca, kategorie `in_budget=False`, grosze `0.10+0.20`). **`hypothesis`**: dla losowych list `TxView` (kwoty z 2 miejscami) `income - expenses == balance`, `sum(by_category) == expenses`, `surplus >= 0`.
- `tests/budget/`: przez API (`auth_client`); transakcje twórz bezpośrednio przez ORM (`Transaction` z `models.py`), żeby nie zależeć od E1-03; izolacja użytkowników.

## Kryteria akceptacji
- [ ] `make lint` przechodzi (w tym kontrakt import-linter: `analytics` bez SQLAlchemy/FastAPI)
- [ ] testy testera przechodzą

## Poza zakresem
F12–F15 (porównania, limity), waluty obce.
