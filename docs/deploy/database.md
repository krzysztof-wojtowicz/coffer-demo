# Baza danych w chmurze: Neon

Produkcyjna baza Coffer to darmowy Postgres w [Neon](https://neon.tech) (plan Free nie wygasa).
Lokalnie nadal używamy Postgresa z `compose.yaml` (`make db-up`), a Neon tylko dla wdrożenia.

```
Render (backend, Frankfurt) ──► Neon (Postgres, AWS eu-central-1 / Frankfurt)
```

## Co jest gotowe w kodzie

- **URL prosto z Neon działa.** Aplikacja i Alembic akceptują `postgres://` i `postgresql://`
  i same zamieniają schemat na `postgresql+psycopg://` (psycopg 3). Parametry
  `?sslmode=require&channel_binding=require` zostają bez zmian. Kod: `coffer/core/db_url.py`,
  walidator w `coffer/core/config.py`.
- **Pula połączeń** (`coffer/core/db.py`): `pool_pre_ping=True` (wykrywa połączenia zerwane,
  gdy Neon uśpił bazę), `pool_size=5`, `max_overflow=5` (maks. 10 połączeń na instancję),
  `pool_recycle=300` s (Neon zamyka bezczynne połączenia).
- **Pooled endpoint:** gdy host zawiera `-pooler`, aplikacja wyłącza prepared statements psycopg
  (`prepare_threshold=None`), bo PgBouncer w trybie transakcyjnym ich nie gwarantuje.
- **Make:** `make migrate-remote` i `make seed-remote` (opis niżej). Nic nie seeduje produkcji
  automatycznie.
- `COFFER_DATABASE_URL` jest ukryty w `repr(Settings)`; nie loguj go i nie wklejaj do repo.

## Direct czy pooled?

Neon pokazuje dwa warianty connection stringa (przełącznik **Connection pooling** w oknie
*Connect*):

| Wariant | Host | Kiedy |
|---|---|---|
| **Direct** (zalecany) | `ep-xxx.eu-central-1.aws.neon.tech` | Migracje Alembic (zawsze), backend na Render z 1 instancją. Pełna sesja Postgresa, najmniej niespodzianek. |
| **Pooled** | `ep-xxx-pooler.eu-central-1.aws.neon.tech` | Wiele instancji / dużo krótkich połączeń (serverless), gdy zbliżasz się do limitu połączeń. |

U nas backend na Render ma jedną instancję i maks. 10 połączeń, a start command uruchamia
`alembic upgrade head` z **tym samym** `COFFER_DATABASE_URL`. Dlatego ustawiamy **direct**.
Migracje przez pooler (PgBouncer, tryb transakcyjny) mogą psuć się na funkcjach sesyjnych,
więc gdybyście kiedyś przeszli na pooled dla aplikacji, migracje odpalajcie direct URL-em
(`make migrate-remote`).

## Krok po kroku

### 1. Konto i projekt

1. Wejdź na <https://neon.tech> → **Sign up** (najprościej przez GitHub lub Google). Karta
   płatnicza nie jest potrzebna.
2. **Create project**:
   - *Project name*: `coffer`
   - *Postgres version*: **16** (taka sama jak lokalnie w `compose.yaml`; 17 też zadziała)
   - *Cloud provider / Region*: **AWS · Europe Central 1 (Frankfurt)** (`aws-eu-central-1`),
     blisko backendu na Render (Frankfurt). Regionu projektu nie da się później zmienić.
   - *Database name*: `neondb` (domyślna, może zostać).
3. Po utworzeniu kliknij **Connect**: wybierz branch `main`, bazę `neondb`, rolę
   `neondb_owner`, **wyłącz** *Connection pooling* (direct) i skopiuj connection string:

   ```
   postgresql://neondb_owner:HASŁO@ep-xxx-yyy-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

   Hasło jest sekretem: nie wklejaj go do repo, issue ani czatu z LLM.

### 2. Migracje z własnego komputera

Z katalogu głównego repo (wymaga `make setup`):

```bash
make migrate-remote COFFER_DATABASE_URL='postgresql://neondb_owner:HASŁO@ep-...neon.tech/neondb?sslmode=require&channel_binding=require'
```

- Apostrofy są potrzebne (URL zawiera `&` i `?`).
- Komenda nie wypisuje URL-a. Gdy pierwsze połączenie trwa ~1 s, to normalne: Neon wybudza
  uśpioną bazę.
- Sprawdzenie wersji schematu:
  `cd src/backend && COFFER_DATABASE_URL='...' uv run alembic current` (powinno być `0004 (head)`
  lub nowsze).

Uwaga: zmienna z wiersza poleceń wygrywa z `.env`. Nie wpisuj URL-a Neon do `.env`, bo wtedy
`make migrate`, `make dev-api` i `make seed` będą działać na produkcji.

### 3. Dane demo (opcjonalnie, świadomie)

```bash
make seed-remote CONFIRM=yes COFFER_DATABASE_URL='postgresql://...'
```

Tworzy konto `demo@coffer.local` ze **znanym hasłem** z `coffer/scripts/seed_demo.py` i
wymyślonymi transakcjami. Rób to tylko na bazie demonstracyjnej; bez `CONFIRM=yes` komenda
odmawia.

### 4. Render (backend)

W usłudze backendu na Render → **Environment** ustaw `COFFER_DATABASE_URL` na **ten sam**
direct connection string (bez zmian, z `postgresql://` i `sslmode=require`). Start command
backendu uruchamia `alembic upgrade head`, więc każde wdrożenie samo dociągnie nowe migracje;
krok 2 jest potrzebny tylko przy pierwszej konfiguracji albo do sprawdzenia, że URL działa.
Szczegóły usługi: [backend.md](backend.md).

## Limity planu Free (stan na 2026, sprawdź <https://neon.tech/pricing>)

- ok. **0,5 GB** danych na projekt (Coffer z danymi demo zajmuje kilka MB),
- limit godzin obliczeniowych na miesiąc (przy 0,25 CU wystarcza na stałą pracę małej
  aplikacji),
- **scale to zero** po ok. 5 min bez ruchu; pierwsze zapytanie po przerwie jest wolniejsze
  (wybudzanie), `pool_pre_ping` odrzuca zerwane połączenia z puli,
- limit połączeń direct zależy od rozmiaru compute (przy 0,25 CU ok. 100); pooler przyjmuje
  ich znacznie więcej,
- krótkie okno przywracania (history / instant restore: kilka godzin wstecz) zamiast
  pełnych backupów.

Po przekroczeniu limitu compute Neon wstrzymuje bazę do końca miesiąca: backend zwraca wtedy
błędy 500, a `/api/health` dalej działa.

## Backup

Darmowe okno przywracania jest krótkie, więc przed ważną zmianą (np. demo, nowa migracja)
zrób zrzut lokalnie (klient `pg_dump` w wersji ≥ wersji serwera; Docker z `compose.yaml` go ma):

```bash
docker run --rm -v "$PWD:/out" postgres:16 \
  pg_dump 'postgresql://neondb_owner:HASŁO@ep-...neon.tech/neondb?sslmode=require' -Fc -f /out/coffer.dump
```

Przywrócenie (do pustej bazy):

```bash
docker run --rm -v "$PWD:/out" postgres:16 \
  pg_restore --no-owner -d 'postgresql://...neondb?sslmode=require' /out/coffer.dump
```

Plik `coffer.dump` zawiera dane użytkowników: nie commituj go.

Alternatywa w konsoli Neon: **Branches → Create branch** robi natychmiastową kopię
(copy-on-write) bazy, z której można wrócić.

## Reset bazy

Usuwa **wszystkie** dane. Do wyboru:

1. **SQL Editor w konsoli Neon** (najprościej):

   ```sql
   DROP SCHEMA public CASCADE;
   CREATE SCHEMA public;
   ```

   potem `make migrate-remote COFFER_DATABASE_URL='...'` (albo redeploy backendu na Render,
   który sam uruchomi migracje).
2. **Alembic:** `cd src/backend && COFFER_DATABASE_URL='...' uv run alembic downgrade base`,
   potem `make migrate-remote ...`.
3. **Nowa baza:** w konsoli Neon *Databases → New database* (lub usuń i załóż projekt od nowa),
   a nowy connection string ustaw w Render i odpal migracje.

## Rozwiązywanie problemów

- `password authentication failed` → zła rola lub hasło; w Neon *Roles → Reset password*,
  zaktualizuj URL w Render.
- `connection ... timeout` przy pierwszym połączeniu → baza się wybudza, spróbuj ponownie.
- `SSL connection is required` → w URL brakuje `?sslmode=require`.
- `prepared statement "_pg3_0" does not exist` → używasz pooled URL bez `-pooler` w hoście
  (np. przez własny proxy); przejdź na direct URL.
- `ModuleNotFoundError: psycopg2` → URL nie przeszedł przez `Settings` (np. własny skrypt
  tworzy engine z surowego URL-a); użyj `coffer.core.db_url.normalize_database_url`.
