# E4-01: Saldo początkowe (środki na kontach realne)

**Fala:** E4/1 · **Zależności:** — · **Role:** implementer + tester · **UC / wymagania:** F26, UC-04

**Status:** zrealizowana poza falą (stan kodu: migracja `0006_opening_balance`, moduł `cash`). Kontrakt poniżej opisuje zaimplementowany stan.

## Cel
Karta „Majątek” pokazuje środki na kontach zgodne ze stanem rzeczywistym: użytkownik podaje saldo początkowe (kwota i data), a środki = saldo + suma transakcji od tej daty do dziś.

## Przeczytaj
- `CLAUDE.md` (ładuje się automatycznie)
- `src/backend/coffer/analytics/net_worth.py`, `src/backend/coffer/budget/{service,api,schemas}.py` (`net_worth`, `GET /api/budget/net-worth`)
- `src/frontend/src/features/budget/NetWorthCard.tsx`, `src/frontend/src/features/auth/AccountPage.tsx`
- `docs/data-model.md` (sekcja 3, zasady modelowania)

## Pliki
- **implementer:** `src/backend/coffer/cash/{models,schemas,service,api}.py` (nowy moduł), migracja `src/backend/alembic/versions/0006_opening_balance.py`, `coffer/analytics/net_worth.py`, `coffer/budget/service.py` (użycie `cash.service`), `coffer/main.py` (router, minimalnie); front: `src/frontend/src/features/budget/NetWorthCard.tsx`, `features/cash/` (formularz salda w `AccountPage` lub na karcie)
- **tester:** `src/backend/tests/cash/`, `tests/analytics/`, testy frontu karty

## Kontrakt
Uproszczenie: jedno saldo początkowe na użytkownika (bez wielu kont; wiele kont poza zakresem).

**Tabela `opening_balances`** (moduł `cash`, migracja `0006`):
- `user_id` integer, PK, FK → `users.id` `ON DELETE CASCADE` (jedno saldo na użytkownika, 1:1),
- `amount` `NUMERIC(14,2)` NOT NULL (może być ujemne),
- `as_of` `DATE` NOT NULL (data salda, włącznie),
- `updated_at` `timestamptz` NOT NULL, `server_default now()`, ustawiane przez ORM.
- Brak CHECK-ów w bazie; walidacja w Pydantic (`OpeningBalanceIn`).

**Schematy:** `OpeningBalanceIn { amount: Decimal, as_of: date }`, `OpeningBalanceOut { amount: "0.00" (string), as_of: "YYYY-MM-DD" }`. Walidacja wejścia (komunikaty po polsku): kwota nie może być `float`, musi być skończona, `|amount| < 1 000 000 000`, maksymalnie 2 miejsca po przecinku; `as_of` nie może być z przyszłości.

**Endpointy** (wszystkie `CurrentUser`; dane zawsze z sesji, cudzego salda nie widać i nie da się go nadpisać):
- `GET /api/cash/opening-balance` → 200 `OpeningBalanceOut`, albo 200 `null`, gdy saldo nie jest ustawione.
- `PUT /api/cash/opening-balance` (body: `amount`, `as_of`) → 200 `OpeningBalanceOut`. Upsert: tworzy albo nadpisuje saldo użytkownika.
- `DELETE /api/cash/opening-balance` → 204. Brak salda też daje 204 (operacja idempotentna).

**Funkcje `cash/service.py`:** `get(db, user_id) -> OpeningBalance | None`, `upsert(db, user_id, data: OpeningBalanceIn) -> OpeningBalance`, `delete(db, user_id) -> None`. Każde zapytanie filtruje po `user_id`.

**Wyliczenie środków** (czyste funkcje w `analytics/net_worth.py`, bez bazy):
- `cash_amounts(dated, today, as_of)` zostawia transakcje z `as_of < date <= today`. Transakcje z dnia `as_of` nie są liczone, bo saldo obowiązuje na koniec tego dnia i już je zawiera. Bez salda (`as_of = None`) liczone są wszystkie transakcje do dziś, jak dotąd.
- `cash_balance(base_amounts, opening=0)` = `quantize(opening + suma)`.
- `budget.service.net_worth` liczy po **wszystkich** transakcjach miesiąca (także w kategoriach poza budżetem), nie tylko po nadwyżce.

**`GET /api/budget/net-worth` (`NetWorthOut`):** `cash_balance`, `portfolio_value`, `net_worth`, `portfolio_complete`, `as_of` (stringi kwot), oraz `opening_balance_set: bool`. Gdy `false`, środki liczone są od zera (zachowanie sprzed karty).

**UI:** gdy `opening_balance_set` jest `false`, karta pokazuje podpowiedź po polsku i link do ustawienia salda. Formularz zapisuje przez `PUT`, a usuwanie przez `DELETE`.

## Kryteria akceptacji
- [ ] `make lint`, testy testera, `make check-web`, `make openapi`
- [ ] środki = saldo + suma transakcji od `as_of` (wyłącznie) do dziś, test z Decimal i `hypothesis`
- [ ] użytkownik A nie widzi ani nie nadpisuje salda użytkownika B

## Poza zakresem
Wiele kont bankowych, przelewy między kontami, waluty inne niż PLN.
