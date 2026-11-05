# E3-01: Profil inwestycyjny (backend)

**Fala:** E3/1 · **Zależności:** E3-00 (modele i migracja `0003`, gotowe) · **Role:** implementer + tester · **UC / wymagania:** UC-05, F30, F02

## Cel
Użytkownik zapisuje i odczytuje swój profil inwestycyjny; moduł udostępnia `get` dla narzędzi agenta.

## Przeczytaj
- `docs/use-cases/UC-05-investment-profile.md`
- `src/backend/coffer/profile/models.py` (gotowy, nie zmieniaj; stałe `HORIZONS`, `RISK_LEVELS`, `ASSET_CLASSES`)
- `src/backend/tests/conftest.py`

## Pliki
- **implementer:** `src/backend/coffer/profile/{api,service,schemas}.py`, w `src/backend/coffer/main.py` tylko dopięcie routera
- **tester:** `src/backend/tests/profile/`

## Kontrakt
- `ProfileIn { horizon: "short"|"medium"|"long", risk: "low"|"medium"|"high", preferred_classes: list["cash"|"deposit"|"stocks"|"etf"|"bonds"|"crypto"|"real_estate"] }`: lista niepusta (422), bez powtórzeń (422 „Klasy aktywów nie mogą się powtarzać”).
- `ProfileOut { horizon, risk, preferred_classes, updated_at: datetime }`
- `GET /api/profile` (`CurrentUser`) → 200 `ProfileOut` albo `null`, gdy profilu nie ma.
- `PUT /api/profile` (`CurrentUser`) → 200 `ProfileOut` (tworzy albo nadpisuje).
- `service.get(db, user_id) -> InvestmentProfile | None`, `service.upsert(db, user_id, data: ProfileIn) -> InvestmentProfile` (commit w serwisie).

## Kryteria akceptacji
- [ ] `make lint` przechodzi
- [ ] testy: brak profilu → `null`; zapis i odczyt; nadpisanie; walidacja (zła wartość, pusta lista, duplikaty); izolacja użytkowników; 401 bez sesji
