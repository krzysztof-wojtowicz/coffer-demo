# Coffer: architektura i plan działania

> Dokument opisuje, **jak** zbudować system opisany w [wizji](vision.md), [wymaganiach](requirements.md), [słowniku](glossary.md) i [przypadkach użycia](use-cases/README.md): technologie, moduły, połączenia między nimi, integrację agenta AI i kolejność prac.

## 0. Decyzje

| Obszar | Decyzja |
|---|---|
| Typ aplikacji | Web, klient–serwer, API-first. Konta, sesje (N02) i klucz LLM poza klientem (N03) i tak wymagają serwera; klient mobilny może dojść później bez zmiany rdzenia. |
| Backend | Python 3.12 + FastAPI (synchronicznie) + SQLAlchemy 2 + Alembic. Python na przedmiocie „Tworzenie Agentów AI w środowisku .NET” uzgodniony z prowadzącym. |
| Frontend | React + TypeScript (Vite, SPA). |
| Baza danych | **PostgreSQL**. MongoDB rozważone i odrzucone (sekcja 2.1). |
| Agent AI | Moduł w tym samym backendzie, za interfejsem, z fallbackiem (N08). Własna pętla narzędzi, bez frameworków agentowych. |
| LLM | **Lokalnie przez Ollamę** (domyślnie `qwen3:8b`: tool use i structured output), bez kosztów i bez wysyłania danych poza komputer. Interfejs `LLMClient` pozwala później dodać darmowy plan chmurowy (np. API zgodne z OpenAI). |
| Repozytorium | **Monorepo:** `docs/`, `src/backend/`, `src/frontend/`, `data/fixtures/`, `.claude/` (system agentów). |
| Środowisko | **Na razie tylko lokalnie** (macOS): Postgres w Dockerze, backend, frontend i Ollama natywnie. Hosting (sekcja 5) to krok na później. |
| Praca zespołu i agentów | Karty zadań w [`docs/tasks/`](tasks/README.md); implementer i tester pracują równolegle z tego samego kontraktu ([`CLAUDE.md`](../CLAUDE.md), `.claude/agents/`). |
| Import CSV | Na start wymyślony format testowy ([`csv-format.md`](csv-format.md)); prawdziwe banki później jako konfiguracja. |
| Hosting (później) | Jeden VPS w UE + Docker Compose + Caddy; front i API pod **jedną domeną** (sekcja 5). |
| MCP | Wewnętrzny rejestr narzędzi od początku; serwer MCP poza semestrem. |
| Termin | Koniec semestru (przełom stycznia i lutego 2027), etapy w sekcji 6. |

## 1. Architektura systemu

```
                       Przeglądarka (React SPA)
                                 │ HTTPS, jedna domena
                                 ▼
                ┌──────────── Caddy (TLS, reverse proxy) ───────────┐
                │  /        → statyczny build frontu                │
                │  /api/*   → api:8000                              │
                └───────────────────────┬───────────────────────────┘
                                        ▼
┌──────────────────────────── api (FastAPI, uvicorn) ─────────────────────────────┐
│  Warstwa HTTP: sesja z ciasteczka → current_user, sprawdzenie Origin (CSRF)     │
│                                                                                 │
│  Rdzeń (działa bez AI):  accounts · transactions · budget · portfolio · profile │
│  Wspierające:            market (ceny, kursy NBP) · analytics (czyste obliczenia)│
│  Opcjonalny:             agent (LLM, narzędzia, walidator) ──────────────┐      │
└──────────┬───────────────────────────────┬───────────────────────────────┼──────┘
           │                               │                               │
     PostgreSQL (db)               NBP / notowania                  Dostawca LLM
           ▲                               ▲                     (+ wyszukiwarka dla F34)
           │                               │
┌──────────┴───────────────────────────────┴──┐
│ worker (ten sam obraz, 1 replika):          │
│ APScheduler → kursy NBP, ceny, pg_dump      │
└─────────────────────────────────────────────┘
```

**Zasada przewodnia: rdzeń liczy, agent interpretuje.** Każda liczba widoczna dla użytkownika (sumy, udziały, zyski, symulacja zakupu) pochodzi z modułu `analytics`. Agent dostaje gotowe wyniki przez narzędzia i pisze tekst z uzasadnieniem. Dzięki temu N04 i N08 są spełnione z konstrukcji, a agent jest testowalny.

Wymagania, które kształtują architekturę:
- **N02, F02:** każdy endpoint poza logowaniem i rejestracją wymaga sesji; każde zapytanie do bazy filtruje po `user_id` z sesji.
- **N03:** klient nigdy nie rozmawia z LLM. Dane do modelu przechodzą przez narzędzia, które zwracają agregaty bez danych osobowych.
- **N04:** kwoty to wyłącznie `Decimal` / `NUMERIC`, sumowanie w jednym miejscu (`analytics`).
- **N08:** rdzeń nie importuje modułu `agent` (sprawdza `import-linter` w CI).
- **N09:** wszystkie dane użytkownika, łącznie z logami agenta, wiszą pod `User` z `ON DELETE CASCADE`.
- **F32, F33, N07:** sugestia to ustrukturyzowany obiekt walidowany przed pokazaniem.

## 2. Stos technologiczny

| Warstwa | Technologie | Rola |
|---|---|---|
| Frontend | Vite, React, TypeScript, React Router, **TanStack Query**, react-hook-form + zod, shadcn/ui, Recharts | SPA; TanStack Query trzyma stan serwera (cache, odświeżanie po mutacjach); Recharts do analiz F10–F23 |
| Kontrakt API | OpenAPI z FastAPI → `openapi-typescript` + `openapi-fetch` | Typy klienta generowane z backendu; CI sprawdza, czy są aktualne |
| Backend | FastAPI (endpointy `def`), Pydantic v2, uvicorn | Synchronicznie: prostszy kod, bez pułapek async SQLAlchemy; SSE przez generator w `StreamingResponse` |
| Dostęp do danych | SQLAlchemy 2 (sync), Alembic, psycopg 3 | Model per-user, migracje wersjonowane w repo |
| Baza | PostgreSQL 16 | `NUMERIC` dla kwot, `ON DELETE CASCADE`, transakcje; `JSONB` dla danych o luźnej strukturze (ImportDraft, AgentRun, źródła sugestii) |
| Uwierzytelnianie | `argon2-cffi`, tabela sesji, ciasteczko HttpOnly + Secure + SameSite=Lax | Usunięcie wiersza sesji natychmiast odbiera dostęp (UC-08), czego JWT nie daje |
| Zadania cykliczne | APScheduler w kontenerze `worker` | Kursy NBP, ceny (F25), backup; jedna replika, więc joby się nie dublują |
| AI | Ollama (`qwen3:8b`, API `/api/chat` przez `httpx`: tool use + structured output) za interfejsem `LLMClient` | Darmowo i lokalnie; szczegóły w sekcji 4 |
| Dane rynkowe | API NBP (kursy), Stooq / Yahoo / Alpha Vantage (notowania, do potwierdzenia licencji) | Za interfejsem `QuoteProvider`, żeby źródło dało się wymienić |
| Jakość | `uv`, `ruff`, `pyright`, `pytest`, `hypothesis`, `import-linter`; ESLint, `tsc` | Python nie ma kompilatora, więc typy i granice modułów sprawdza CI |
| Infrastruktura | Docker Compose, Caddy, GitHub Actions, GHCR | Jedno środowisko dla 4 osób i produkcji |

### 2.1 Odrzucone alternatywy

- **MongoDB zamiast PostgreSQL.** Dane Coffer są relacyjne, a najtwardsze wymagania to właśnie to, co daje baza relacyjna:
  - N04: `Decimal128` istnieje, ale bez schematu łatwo zapisać kwotę jako `double`, a sumy w pipeline’ach trudniej kontrolować;
  - N09: brak kluczy obcych i kaskad, więc usuwanie konta trzeba ręcznie utrzymywać dla każdej kolekcji;
  - UC-02: atomowe zatwierdzenie importu wymaga transakcji wielodokumentowych, czyli replica setu także lokalnie;
  - wycena portfela łączy dane per-user (Position) z globalnymi (Instrument, PriceQuote, FxRate), co w Mongo oznacza `$lookup` albo duplikację cen;
  - SQLAlchemy nie obsługuje Mongo, a popularne ODM (Beanie) są asynchroniczne, co kłóci się z decyzją o synchronicznym backendzie.

  Miejsca, gdzie model dokumentowy pasuje (logi agenta, podgląd importu), pokrywa `JSONB`.
- **Next.js:** brak potrzeby SEO i SSR, a dodałby drugi serwer (Node) obok Pythona.
- **Front na Vercel/Netlify, API osobno:** rozbija jedną domenę. Ciasteczko sesji wymagałoby `SameSite=None` i CORS.
- **Darmowe PaaS (Render, Railway itp.):** usypiają usługi (worker i joby przestają działać), darmowe bazy bywają czasowe.
- **Frameworki agentowe (LangChain itp.):** pętla narzędzi to kilkadziesiąt linii; własna jest przejrzysta, testowalna i pokazuje temat przedmiotu w kodzie.

## 3. Moduły i ich połączenia

### 3.1 Struktura kodu

```
src/backend/coffer/
  core/          konfiguracja, sesja DB, money.py (Decimal, ROUND_HALF_UP), auth dependency, błędy
  accounts/      ┐
  transactions/  │ każdy moduł:
  budget/        │   api.py      router FastAPI (cienki: walidacja, wywołanie serwisu)
  portfolio/     │   service.py  logika + jedyny publiczny interfejs modułu
  profile/       │   models.py   tabele SQLAlchemy
  market/        │   schemas.py  modele Pydantic (wejście/wyjście API)
  analytics/     ┘ (analytics: tylko czyste funkcje, bez models.py i bez bazy)
  agent/         llm.py, tools/, runner.py, workflows/, validator.py, anonymizer.py, prompts/
  worker.py      punkt wejścia kontenera worker
src/frontend/src/
  features/{auth,transactions,budget,portfolio,profile,assistant}/
  api/           wygenerowany klient + hooki TanStack Query
```

Moduły komunikują się **tylko przez `service.py`**: żaden moduł nie czyta tabel innego modułu bezpośrednio.

### 3.2 Graf zależności (egzekwowany przez `import-linter`)

```
agent ──► profile, portfolio, budget, transactions, market, analytics   (tylko service)
budget ──► transactions, analytics
portfolio ──► market, analytics
transactions ──► market (kursy NBP)
accounts ──► (nikt; usuwanie konta przez kaskady w bazie)
analytics ──► nic (czyste funkcje na Decimal i dataclassach)
rdzeń ──✗──► agent
```

### 3.3 Moduły

| Moduł | Odpowiedzialność | Encje | Wymagania | Główne endpointy |
|---|---|---|---|---|
| `accounts` | Rejestracja, logowanie, sesje, usunięcie konta | User, Session | F01, F02, N01, N02, N09; UC-01, UC-08 | `POST /api/auth/register`, `/login`, `/logout`, `DELETE /api/me` |
| `transactions` | CRUD transakcji, import CSV (parser per bank z konfiguracji), deduplikacja (multizbiór data+kwota+opis), kategoryzacja (reguły, uczenie z poprawek) | Transaction, Category, CategorizationRule, ImportDraft | F03–F08; UC-02, UC-03 | `/api/transactions`, `POST /api/imports` (podgląd), `POST /api/imports/{id}/commit` |
| `budget` | Limity, widoki analiz miesięcznych | SpendingLimit (później SavingsGoal) | F10–F15 | `GET /api/budget/{miesiac}`, `/api/limits` |
| `portfolio` | Pozycje (model jednolity dla wszystkich klas), wycena | Position | F20–F24; UC-04 | `/api/positions`, `GET /api/portfolio/summary` |
| `profile` | Profil inwestycyjny | InvestmentProfile | F30; UC-05 | `GET/PUT /api/profile` |
| `market` | Instrumenty, ceny, kursy NBP: cache, odświeżanie, pobieranie na żądanie z timeoutem, data pobrania | Instrument, PriceQuote, FxRate (globalne) | F25, N07, Z4 | `GET /api/market/quote/{ticker}` |
| `analytics` | Sumy, nadwyżka, porównania, udziały klas, zysk/strata, symulacja zakupu | brak | N04, F10–F15, F22–F24, F37 | brak (używany przez inne moduły) |
| `agent` | Sugestie i wyszukiwanie informacji z użyciem LLM | Suggestion, AgentRun | F31–F35, F37, N03, N07, N08 | sekcja 4.5 |

### 3.4 Model danych (skrót)

- **User** (email, hash hasła, zgoda Z6; waluta bazowa stała PLN w v1)
  - Session, Transaction, ImportDraft (`JSONB` z wierszami, TTL), CategorizationRule, SpendingLimit, Position, InvestmentProfile, Suggestion, AgentRun (`JSONB` z przebiegiem), wszystkie z `ON DELETE CASCADE`.
- **Transaction:** data, kwota i waluta oryginalna, kurs i data kursu, `kwota_bazowa` zaokrąglona per transakcja (sumy liczone tylko z niej), opis, kategoria, źródło (ręczna/import), flaga „do weryfikacji”.
- **Category:** systemowe, domyślna „Inne”, flaga `wliczana_do_budzetu` („Przelewy własne”, „Inwestycje” nie zaniżają nadwyżki).
- **Position:** klasa, nazwa, opcjonalny Instrument, ilość, cena zakupu, waluta, kurs zakupu, data, `ostatnia_cena_reczna`. Gotówka: ilość = kwota, cena 1; nieruchomość: ilość 1, cena = wartość. Dokupienie to nowa pozycja (lot), agregacja w widoku.
- Globalne: **Instrument** (ticker, klasa, waluta), **PriceQuote** (cena, data notowania, data pobrania), **FxRate** (kurs, data tabeli NBP).
- Precyzja: kwoty `NUMERIC(14,2)`, kursy `NUMERIC(18,8)`, ilości `NUMERIC(28,8)`.

### 3.5 Frontend

- Każdy katalog w `features/` odpowiada modułowi API; `assistant/` obsługuje sugestie i SSE.
- Kwoty przychodzą jako stringi i są tylko wyświetlane (formatowanie `Intl.NumberFormat('pl-PL')`). Frontend nie liczy sum.
- Wszystkie teksty po polsku (N06), w jednym pliku komunikatów, żeby nie rozpraszać ich po komponentach.
- Widoki rdzenia nie zależą od asystenta: blok AI to osobny komponent, który przy błędzie pokazuje komunikat, a reszta strony działa (N08).

### 3.6 Kluczowe przepływy

1. **Import CSV (UC-02):** upload → `transactions` parsuje plik wg konfiguracji banku (kodowanie, separator, kolumny; format `1 234,56`) → `market` daje kursy NBP (dzień bez tabeli: ostatni opublikowany kurs) → deduplikacja względem bazy (multizbiór) → kategoryzacja regułami → zapis `ImportDraft` → użytkownik poprawia podgląd → commit: ponowna deduplikacja i zapis w jednej transakcji DB.
2. **Analiza miesięczna (F10–F15):** `budget.service` pobiera transakcje miesiąca (i 3 poprzednich) z `transactions.service` → `analytics` liczy sumy per kategoria, nadwyżkę, zmiany, przekroczenia limitów → endpoint zwraca gotowy widok.
3. **Wycena portfela (F22–F24):** worker codziennie pobiera ceny instrumentów obecnych w portfelach i kursy NBP → `portfolio.service` łączy pozycje z ostatnimi cenami z `market` → `analytics` liczy wartość, udziały klas i zysk/stratę → pozycje bez aktualnej ceny oznaczone jako nieaktualne (UC-04 6a).

## 4. Agent i LLM: integracja

### 4.1 Komponenty modułu `agent`

```
endpoint /api/agent/* (SSE)
   │
   ▼
Workflow (F31, F37)  albo  AgentRunner (F34–F35)     ← wybór per zadanie (4.3)
   │                          │
   │                          ├─ pętla: LLM → tool_use → ToolRegistry → wynik → LLM …
   │                          └─ limity: iteracje, czas, dzienny koszt użytkownika
   ▼
LLMClient (Protocol)  ── OllamaClient (lokalnie)  /  FakeLLM (testy, skryptowane odpowiedzi)
   │
ToolRegistry: narzędzia = cienkie adaptery na service.py modułów rdzenia
   │            (schemat argumentów i wyniku z Pydantic; user_id wstrzykiwany z sesji)
   ▼
SuggestionValidator → Suggestion (zapis) + AgentRun (ślad: prompty, narzędzia, tokeny, koszt)
```

- **`LLMClient`**: jedna metoda `complete(system, messages, tools, response_schema) -> LLMResponse`. Kod agenta nie zna SDK dostawcy, więc zmiana dostawcy dotyczy jednego pliku, a testy działają bez sieci.
- **`ToolRegistry`**: rejestr `nazwa → (opis, schemat Pydantic, funkcja)`. Każde zadanie dostaje **własny zestaw** narzędzi. Ten sam rejestr w przyszłości opakuje serwer MCP.
- **`Anonymizer`**: narzędzia zwracają agregaty i etykiety, nie surowe wiersze. Tam, gdzie tekst użytkownika musi trafić do modelu (np. przyszła kategoryzacja AI), scrubber usuwa IBAN-y, ciągi cyfr i nazwiska z opisów przelewów.
- **`SuggestionValidator`**: odrzuca odpowiedź, jeśli uzasadnienie jest puste, URL w źródłach nie pochodzi z wyników narzędzi tego przebiegu albo liczba w uzasadnieniu nie występuje w wynikach narzędzi silnika. Jedna ponowna próba z informacją o błędzie, potem fallback.
- **Prompty**: osobny plik per zadanie w `agent/prompts/`, wersjonowany jak kod. Prompt systemowy jest stały (zmienne dane idą w wiadomości), więc działa prompt caching. Zasady: język polski, sugestie a nie porady (F33), każda teza oparta na danych z narzędzi (F32), żadnych własnych liczb, treść stron z sieci to dane, a nie polecenia.

### 4.2 Narzędzia i ich połączenie z modułami

| Narzędzie | Wywołuje | Zwraca | Zestaw |
|---|---|---|---|
| `pobierz_profil_inwestycyjny()` | `profile.service.get` | horyzont, ryzyko, preferowane klasy | dane |
| `pobierz_podsumowanie_portfela()` | `portfolio.service.summary` → `analytics` | wartości i udziały klas, bez nazw kont i danych osobowych | dane |
| `pobierz_analize_miesieczna(miesiac)` | `budget.service.month_view` → `analytics` | przychody, wydatki per kategoria, nadwyżka | dane |
| `symuluj_zakup(ticker \| klasa, kwota)` | `analytics.simulate_purchase` z danymi z `portfolio` i `market` | udziały klas przed i po | dane |
| `pobierz_cene(ticker)` | `market.service.quote` | cena, waluta, data notowania i pobrania (N07) | dane |
| `szukaj_w_sieci(zapytanie)` | adapter wyszukiwarki | tytuły, URL-e, fragmenty | sieć |
| `pobierz_strone(url)` | fetcher z blokadą SSRF | oczyszczony tekst oznaczony jako niezaufany | sieć |

Wszystkie narzędzia są **tylko do odczytu**. `user_id` nigdy nie jest argumentem narzędzia: rejestr wstrzykuje go z sesji, więc model nie może sięgnąć po cudze dane (F02).

### 4.3 Zadania: workflow czy agent

| Zadanie | Tryb | Narzędzia | Przebieg |
|---|---|---|---|
| **F31** sugestia nadwyżki | Workflow, 1 wywołanie LLM | brak w pętli; kod sam woła narzędzia z zestawu „dane” | 1) kod pobiera analizę miesiąca, portfel i profil; 2) gdy nadwyżka ≤ 0, odpowiedź bez LLM; 3) LLM dostaje dane i zwraca `SuggestionDraft` (structured output); 4) walidator; 5) zapis `Suggestion` |
| **F37 / UC-07** ocena zakupu | Workflow | jw. + `symuluj_zakup`, `pobierz_cene` | 1) cena z cache, na żądanie albo ręczna (UC-07 2a); 2) `analytics` liczy udziały przed i po; 3) UI dostaje porównanie **od razu** (bez AI); 4) LLM interpretuje wynik w kontekście profilu; 5) walidator → ocena jako dodatkowy blok |
| **F34–F35** informacje o spółce | Agent (pętla tool use) | tylko „sieć” | model sam decyduje, ile razy szukać i które strony pobrać; limit np. 6 iteracji i 60 s; wynik: podsumowanie + źródła z datą pobrania |
| F07 kategoryzacja (po semestrze) | 1 wywołanie wsadowe, enum kategorii | brak | po regułach, tylko dla nierozpoznanych; opisy przez scrubber |
| F36, F38 (po semestrze) | Agent | rozdzielone kroki: badawczy (sieć, bez danych) i dopasowanie (dane, bez sieci) | — |

**Rozdzielenie uprawnień:** zadanie z dostępem do sieci nie ma narzędzi z danymi użytkownika, a zadania z danymi nie mają sieci. Dzięki temu strona z ukrytymi instrukcjami nie może wyprowadzić danych portfela (np. wpisując je w URL w `pobierz_strone`).

### 4.4 Format odpowiedzi

```
SuggestionDraft {                        // zwraca LLM (structured output)
  podsumowanie: string
  uzasadnienie: [{ teza, odwolanie_do_danych: "portfel"|"budzet"|"profil", wartosc }]  // min. 1 (F32)
  zrodla: [{ url, tytul }]                                                              // F35
  ryzyka: string[]
}
Suggestion = SuggestionDraft + typ + zastrzeżenie (F33) + data danych rynkowych (N07) + snapshot profilu
```

Pola `typ`, zastrzeżenie i daty ustawia system, nie model. Ten sam model Pydantic służy do zapisu w bazie, odpowiedzi API i typów TypeScript.

### 4.5 Przebieg jednego żądania

```
UI ──POST /api/agent/surplus {miesiac}──► api
api ──SSE: status "liczę nadwyżkę"──► UI
api → budget/portfolio/profile.service → analytics          (bez LLM)
api ──SSE: dane deterministyczne (nadwyżka, udziały)──► UI  (pokazywane zawsze)
api → sprawdzenie dziennego limitu kosztu
api → LLMClient.complete(...) → SuggestionValidator
     ├─ OK     → zapis Suggestion + AgentRun → SSE: sugestia ──► UI
     └─ błąd / timeout / limit → AgentRun z błędem → SSE: "asystent niedostępny" ──► UI
```

Endpointy: `POST /api/agent/surplus`, `POST /api/agent/purchase-impact`, `POST /api/agent/company-info` (SSE), `GET /api/suggestions` (historia; zmiana profilu nie zmienia zapisanych sugestii, UC-05).

### 4.6 Fallback i limity (N08)

- Brak klucza LLM, timeout lub błąd dostawcy → endpoint zwraca część deterministyczną i status `ai_niedostepne`; rdzeń nie ma żadnego wywołania LLM.
- Limity w konfiguracji: maks. iteracji, maks. czas przebiegu, dzienny koszt na użytkownika (liczony z tokenów w `AgentRun`).
- Każde SSE zajmuje wątek puli (domyślnie 40). W skali projektu to wystarcza; znane ograniczenie.

### 4.7 Testy agenta

- `FakeLLM` ze skryptowanymi odpowiedziami: testy pętli, limitów, fallbacku i walidatora bez sieci i bez kosztów.
- Kilkanaście scenariuszy (pusty portfel, brak profilu, ujemna nadwyżka, AI niedostępne, strona ze złośliwymi instrukcjami) uruchamianych na prawdziwym modelu ręcznie przed oddaniem, z zapisem w `AgentRun`.
- Testy automatyczne: odpowiedź przechodzi walidator, liczby w tekście zgadzają się z wynikiem silnika, źródła mają datę.

## 5. Środowisko i wdrożenie

### 5.1 Teraz: tylko lokalnie
- `compose.yaml` zawiera tylko `db` (Postgres 16, baza `coffer` i `coffer_test`). Backend (`make dev-api`), frontend (`make dev-web`) i Ollama działają natywnie na macOS.
- Front przez Vite z proxy `/api → localhost:8000`, więc ciasteczko sesji działa jak na produkcji (jedno pochodzenie).
- `make check` lokalnie zastępuje CI; testy równoległych agentów używają osobnych baz (`COFFER_TEST_DB`).
- Instrukcja uruchomienia demo: `README.md`.

### 5.2 Później: hosting
Usługi w `compose.yaml` (lokalnie i na produkcji ten sam plik, nadpisania w `compose.prod.yaml`):

| Usługa | Obraz | Uwagi |
|---|---|---|
| `caddy` | Caddy + build frontu | TLS z Let’s Encrypt, `/api/*` → api, reszta → pliki SPA; buforowanie wyłączone dla SSE |
| `api` | backend | uvicorn, `.env` z kluczem LLM, sekretem i hasłem bazy |
| `worker` | ten sam obraz, inny `command` | dokładnie 1 replika |
| `migrate` | ten sam obraz | `alembic upgrade head` jednorazowo przy wdrożeniu |
| `db` | `postgres:16` | wolumen; nocny `pg_dump` przez worker do zewnętrznego miejsca |

- **Jedna domena:** ciasteczko HttpOnly + SameSite=Lax działa bez CORS. Ochrona CSRF: middleware odrzuca żądania modyfikujące z obcym nagłówkiem `Origin`.
- **CI/CD (GitHub Actions):** lint + typy + testy (z Postgresem jako service) → build obrazów → push do GHCR → na `main` deploy przez SSH: `docker compose pull && docker compose up -d`.
- **Serwer:** VPS w UE, 2 vCPU / 4 GB RAM wystarczą (Ollama na VPS wymagałaby więcej; wtedy raczej darmowy plan chmurowego LLM). Dostawca do wyboru, gdy projekt wyjdzie poza środowisko lokalne: najpierw sprawdzić kredyty studenckie (Azure for Students, GitHub Student Pack), inaczej tani VPS (np. Hetzner). Fallback dla bazy: zarządzany Postgres (Neon, Supabase).
- Sekrety tylko w `.env` na serwerze i w GitHub Secrets; w repo `.env.example`.

## 6. Plan działania

F30–F33 mają priorytet **M**, więc agent M idzie przed S rdzenia. Przy opóźnieniu odpada to, co opcjonalne. Daty orientacyjne.

Proponowany podział na 4 osoby (każda ma backend i front swojego obszaru):
- **A:** `accounts`, `core`, infrastruktura (Compose, CI/CD, VPS), testy N02/N09,
- **B:** `transactions` (CRUD, import, deduplikacja, kategoryzacja), `budget`,
- **C:** `portfolio`, `market`, `analytics`,
- **D:** `agent` (LLMClient, narzędzia, workflow, walidator), `profile`, widok asystenta.

### Etap 0: domknięcie specyfikacji (do 8.11.2026)
- [ ] Rozstrzygnąć listę z sekcji 7 i zapisać decyzje w specyfikacji.
- [x] Dopisać brakujące UC: logowanie, ręczna transakcja, analiza miesięczna, sugestia nadwyżki, informacje o spółce (UC-09..UC-13).
- [x] LLM: Ollama lokalnie; środowisko tylko lokalne; monorepo; testowy format CSV.
- [x] Karty zadań Etapu 1 w `docs/tasks/`.

**Gotowe, gdy:** zespół przyjął decyzje, każdy zna swój obszar.

### Etap 1: szkielet end-to-end (do 15.11.2026)
- [ ] A: repo (`src/backend`, `src/frontend`), `uv`, Vite, Compose (baza), `make check` (ruff, pyright, pytest, tsc), `import-linter` z grafem z 3.2.
- [ ] A: rejestracja, logowanie, sesje, middleware Origin.
- [ ] B: tabela Transaction + ręczne dodanie (F03), lista.
- [ ] C: `core/money.py` + `analytics.month_summary` (suma miesiąca, nadwyżka F11).
- [ ] D: `LLMClient` + `OllamaClient` + `FakeLLM`, workflow F31 w wersji minimalnej (1 prawdziwe wywołanie, fallback przy niedostępnym modelu).
- [ ] Wszyscy: generowanie typów TS z OpenAPI.

Realizacja: karty E1-01..E1-07 w [`docs/tasks/`](tasks/README.md) (fale równoległe, implementer + tester).

**Gotowe, gdy:** lokalnie można się zarejestrować, dodać transakcję, zobaczyć nadwyżkę i dostać od lokalnego LLM sugestię; z `COFFER_LLM_PROVIDER=none` lub wyłączoną Ollamą aplikacja działa dalej.

### Etap 2: rdzeń M (do 13.12.2026)
- [ ] A: test „401 dla każdej trasy bez sesji” i test dostępu do cudzych zasobów (N02, F02); argon2 (N01).
- [ ] B: edycja i usuwanie (F06), zmiana kategorii (F08), import CSV dla 2 banków z podglądem `ImportDraft` (F04); do czasu F07 kategoria „Inne” z flagą „do weryfikacji”.
- [ ] B + C: analiza miesięczna per kategoria (F10, F11), testy `hypothesis` dla N04.
- [ ] C: `market`: kursy NBP (job + na żądanie); `portfolio`: CRUD pozycji (F20, F21), wartość i udziały klas (F22, F23) po cenie zakupu, oznaczone jako nieaktualne.
- [ ] Wszyscy: UI po polsku (N06).

**Gotowe, gdy:** UC-01–UC-04 da się przejść w aplikacji na produkcji.

### Etap 3: agent M (do 3.01.2027)
- [ ] D: profil inwestycyjny (F30, UC-05).
- [ ] D: `ToolRegistry` z zestawem „dane”, pełny workflow F31 ze structured output, `SuggestionValidator`, zastrzeżenie (F31–F33).
- [ ] D: `AgentRun`, limity kosztu, SSE ze statusem, fallback w UI (N08).
- [ ] D + C: anonimizacja w narzędziach i test, że w promptach nie ma e-maila, nazwisk ani numerów kont (N03).
- [ ] D: scenariusze testowe z 4.7 na `FakeLLM`.

**Gotowe, gdy:** sugestia nadwyżki działa z uzasadnieniem z danych, przechodzi walidator, zapisuje się w historii, a test z wyłączonym LLM przechodzi.

### Etap 4: priorytety S (do 24.01.2027), w tej kolejności
1. **F34–F35 + N07:** agent z narzędziami sieciowymi (jedyna prawdziwa pętla agenta, więc bez tego projekt na przedmiot o agentach nie ma agenta).
2. **F37 / UC-07:** `analytics.simulate_purchase` + workflow oceny.
3. **N08** (pełny), **N09** (usuwanie konta, test po metadanych).
4. **F25 / F24:** job cen, zysk/strata.
5. **F05** (deduplikacja), **F07** (reguły kategoryzacji z poprawek).
6. **F12–F15:** porównania i limity (odpadają pierwsze przy braku czasu).

**Gotowe, gdy:** UC-07 i UC-08 przechodzą, a agent informacyjny zwraca podsumowanie ze źródłami i datami.

#### Etap 4a: po serii zmian UI/UX (karty E4-01..E4-06)
Stan: 5 zakładek (Podsumowanie, Transakcje, Portfel, Doradca AI, Konto), edycja transakcji (`PATCH /api/transactions/{id}`), karta „Majątek” (`GET /api/budget/net-worth`, `analytics/net_worth.py`), jeden panel Doradcy AI (nadwyżka + portfel; doradca zapisuje sugestię `advisor`), nowy UI kit. Znane luki i kolejne kroki:
- [x] E4-01: saldo początkowe (`opening_balances`, migracja `0006`, sekcja w Koncie).
- [ ] E4-02: filtry, sortowanie i paginacja transakcji po stronie serwera (zakres dat poza miesiącem).
- [ ] E4-03: data aktualizacji cen i kursów w portfelu.
- [ ] E4-04: wykres historii majątku (po E4-01).
- [ ] E4-05: testy e2e Playwright kluczowych przepływów (po E4-01, E4-02).
- [ ] E4-06: dostępność nowych komponentów UI (klawiatura, ARIA, fokus).

Karty: [`docs/tasks/README.md`](tasks/README.md). Równolegle (fala 1) mogą iść E4-01, E4-02, E4-03, E4-06 (rozłączne pliki).

### Bufor (do oddania)
Stabilizacja, dane demo, sprawdzone odtworzenie backupu, prezentacja.

**Ryzyko:** etapy 3 i 4 obejmują przerwę świąteczną i sesję. Kolejność w Etapie 4 ustala, co odpada.

**Poza semestrem:** F09, F16–F18, F36 (UC-06), F38, N05, F07 przez AI, MCP, PWA.

## 7. Do rozstrzygnięcia w Etapie 0

1. Formaty CSV prawdziwych banków (na start format testowy z `csv-format.md`), opisane konfiguracją, nie klasami.
2. Kategorie systemowe: „Inne” jako domyślna, „Przelewy własne” i „Inwestycje” poza budżetem.
3. Czy zmiana kategorii uczy kategoryzator (rekomendacja: tak, tabela reguł).
4. Źródło notowań: limity i licencja.
5. Hosting i ewentualny chmurowy LLM (gdy wyjdziemy poza środowisko lokalne).
6. Zasady hasła, potwierdzenie e-mail, enumeracja kont (UC-01).
7. Propozycje zmian w specyfikacji (przyjąć lub odrzucić):
   - F05: porównanie jako multizbiór (plik ma 2 identyczne bilety, baza 1, więc importujemy 1),
   - F20 i słownik: pozycje bez tickera w modelu jednolitym,
   - N03: opisy transakcji jako dane wymagające anonimizacji,
   - UC-06: status „poza zakresem semestru”,
   - waluta bazowa stała PLN w v1.

## 8. Weryfikacja

| Wymaganie | Test |
|---|---|
| N02, F02 | Iteracja po wszystkich trasach OpenAPI: bez sesji 401; dostęp do zasobu innego użytkownika 404 |
| N04 | `hypothesis`: suma w podsumowaniu = suma `kwota_bazowa` transakcji, także z walutami obcymi |
| N08 | `import-linter` w CI + test integracyjny z niedostępnym LLM |
| N09 | Po usunięciu konta żadna tabela (z metadanych SQLAlchemy) nie ma wierszy użytkownika |
| N03 | Test promptów z `FakeLLM`: brak e-maila, nazwisk i numerów kont |
| F32, F33, N07 | Walidator na scenariuszach z 4.7 |
| CSRF | Żądanie modyfikujące z obcym `Origin` → 403 |
| Backup | Przed demo: odtworzenie bazy z `pg_dump` na czystym kontenerze |

Każdy z UC-01..05, UC-07 i UC-08 przechodzimy ręcznie na produkcji na koniec etapu, w którym powstaje.
