# Uruchomienie, konfiguracja i hosting

Dokument dla deweloperów: jak uruchomić Coffer lokalnie, skonfigurować asystenta AI, testować i rozwijać projekt. Opis produktu z perspektywy użytkownika jest w [README](../README.md). Ścieżki w poleceniach są względem katalogu głównego repozytorium.

Powiązane dokumenty:
- [Wdrożenie produkcyjne](deploy/): baza [Neon](deploy/database.md), backend [Render](deploy/backend.md), frontend [Vercel](deploy/frontend.md), [CI](deploy/ci.md)
- [Architektura systemu (diagramy)](architecture.md)

## Spis treści

1. [Coffer w skrócie (dla deweloperów)](#1-coffer-w-skrócie-dla-deweloperów)
2. [Wymagania](#2-wymagania)
3. [Pierwsze uruchomienie krok po kroku](#3-pierwsze-uruchomienie-krok-po-kroku)
4. [Konfiguracja](#4-konfiguracja) (w tym [alternatywny asystent AI: Gemini / OpenAI / Claude](#alternatywny-asystent-ai-gemini--openai--claude))
5. [Najczęstsze problemy](#5-najczęstsze-problemy)
6. [Jak to działa](#6-jak-to-działa)
7. [Struktura kodu](#7-struktura-kodu)
8. [Testy i jakość](#8-testy-i-jakość)
9. [Praca z agentami AI](#9-praca-z-agentami-ai)

## 1. Coffer w skrócie (dla deweloperów)

**Coffer** to aplikacja do zarządzania finansami osobistymi z lokalnym asystentem AI. Użytkownik importuje lub dodaje transakcje, widzi analizę miesiąca (przychody, wydatki, nadwyżka) i dostaje sugestię wykorzystania nadwyżki. Liczy rdzeń aplikacji, a model językowy (Ollama, działa lokalnie) tylko interpretuje gotowe agregaty. Projekt powstaje na Politechnice Warszawskiej w ramach przedmiotów _Inżynieria Oprogramowania 1_ (specyfikacja) i _Tworzenie Agentów AI w środowisku .NET_ (integracja z agentem).

| Działa | Jeszcze nie ma |
|---|---|
| konto użytkownika (rejestracja, logowanie) | kursy NBP (kursy walut pochodzą z Yahoo Finance) |
| transakcje (dodawanie, lista, usuwanie) | edycja transakcji |
| import CSV z deduplikacją | |
| analiza miesiąca (kategorie, nadwyżka) | |
| profil inwestycyjny | |
| asystent AI: sugestia nadwyżki, historia, ślad przebiegu | |
| portfel inwestycyjny: pozycje, wycena w PLN, alokacja | |
| doradca AI portfela (dane rynkowe z Yahoo Finance, serwer MCP) | |

## 2. Wymagania

| Narzędzie | Wersja | Po co | macOS (Homebrew) |
|---|---|---|---|
| Git | dowolna | klonowanie repo | `brew install git` |
| Docker Desktop | aktualny | Postgres 16 w kontenerze | `brew install --cask docker` (uruchom aplikację) |
| uv | aktualny | sam instaluje Pythona 3.12 i zależności backendu | `brew install uv` |
| Node.js + npm | >= 20 | frontend (React, Vite) | `brew install node` |
| Ollama | aktualny | lokalny model AI (opcjonalnie) | `brew install --cask ollama` |

Model: `ollama pull qwen3:8b` (ok. 5 GB, zalecane min. 16 GB RAM). Mniejsza alternatywa: `ollama pull qwen3:4b` i `COFFER_OLLAMA_MODEL=qwen3:4b` w `.env`.

Linux / Windows: zainstaluj te same narzędzia własnym menedżerem pakietów (Docker Engine albo Docker Desktop, [uv](https://docs.astral.sh/uv/), Node.js, [Ollama](https://ollama.com)). Na Windows pracuj w WSL2 (z włączoną integracją Dockera), potrzebne jest też `make`.

Wolne porty: **5432** (Postgres), **8000** (API), **5173** (frontend), **11434** (Ollama).

## 3. Pierwsze uruchomienie krok po kroku

Wszystkie polecenia z katalogu głównego repozytorium.

| Krok | Komenda | Co robi |
|---|---|---|
| 1 | `git clone <adres-repozytorium> coffer && cd coffer` | pobiera kod |
| 2 | `cp .env.example .env` | (opcjonalnie) plik konfiguracji; bez niego działają wartości domyślne |
| 3 | `make setup` | instaluje zależności backendu (`uv sync`) i frontendu (`npm install`) |
| 4 | `make db-up` | uruchamia Postgresa w Dockerze i czeka na gotowość |
| 5 | `make migrate` | tworzy schemat bazy i kategorie systemowe (Alembic) |
| 6 | `make seed` | tworzy konto demo i transakcje z 3 ostatnich miesięcy (można powtarzać: transakcje demo są tworzone od nowa) |
| 7 | `make dev-api` | API na `http://localhost:8000` (terminal 1) |
| 8 | `make dev-web` | frontend na `http://localhost:5173` (terminal 2) |

Otwórz [http://localhost:5173](http://localhost:5173) i zaloguj się kontem demo:

- e-mail: `demo@coffer.local`
- hasło: `coffer-demo-2026`

**Jak sprawdzić, że działa**
- `curl localhost:8000/api/health` zwraca status `ok`.
- W panelu asystenta widać status modelu: „`<model>` · dostępny”, „Model niedostępny” albo „AI wyłączone”.

## 4. Konfiguracja

Zmienne środowiskowe `COFFER_*` (z procesu albo z pliku `.env` w katalogu głównym). Wszystkie są opcjonalne.

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `COFFER_DATABASE_URL` | `postgresql+psycopg://coffer:coffer@localhost:5432/coffer` | adres bazy (SQLAlchemy + psycopg 3) |
| `COFFER_ALLOWED_ORIGINS` | `["http://localhost:5173","http://localhost:8000"]` | dozwolone originy dla żądań zmieniających dane (lista JSON) |
| `COFFER_SESSION_TTL_DAYS` | `14` | ważność sesji w dniach |
| `COFFER_COOKIE_SECURE` | `false` | `true`, gdy aplikacja działa przez HTTPS |
| `COFFER_LLM_PROVIDER` | `ollama` | dostawca LLM: `ollama`, `openai`, `gemini` albo `none` |
| `COFFER_OLLAMA_URL` | `http://localhost:11434` | adres serwera Ollama |
| `COFFER_OLLAMA_MODEL` | `qwen3:8b` | nazwa modelu |
| `COFFER_OPENAI_API_KEY` | (pusty) | klucz API OpenAI (dla `openai`) |
| `COFFER_OPENAI_MODEL` | `gpt-4o-mini` | model OpenAI |
| `COFFER_OPENAI_BASE_URL` | `https://api.openai.com/v1` | adres API zgodnego z OpenAI |
| `COFFER_GEMINI_API_KEY` | (pusty) | klucz API Google Gemini (dla `gemini`) |
| `COFFER_GEMINI_MODEL` | `gemini-3.5-flash-lite` | model Gemini |
| `COFFER_LLM_FALLBACKS` | (pusty) | zapasowe modele `provider:model`, np. `gemini:gemini-3.8-flash` |
| `COFFER_ADVISOR_TIMEOUT_S` | `60` | łączny limit czasu doradcy inwestycyjnego (s), < 110 |
| `COFFER_LLM_TIMEOUT_S` | `90` | limit czasu żądania do modelu (s) |
| `COFFER_AGENT_DAILY_LIMIT` | `50` | maks. przebiegów agenta na użytkownika na dobę |
| `COFFER_AGENT_MAX_ATTEMPTS` | `2` | próby wywołania modelu (1 + 1 poprawka po błędzie walidacji) |

- **Wyłączenie AI:** `COFFER_LLM_PROVIDER=none` w `.env` (restart `make dev-api`). Reszta aplikacji działa bez zmian.
- **Zmiana modelu:** `ollama pull <model>` i `COFFER_OLLAMA_MODEL=<model>`.

### Alternatywny asystent AI: Gemini / OpenAI / Claude

Domyślnie asystent korzysta z lokalnej Ollamy. Zamiast niej można użyć modelu w chmurze: Google Gemini, Anthropic Claude albo OpenAI (lub dowolnego API zgodnego z OpenAI, np. LM Studio, vLLM, OpenRouter).

**Jak przełączyć.** W `.env` ustaw dostawcę i klucz, potem zrestartuj `make dev-api`:

```env
# Gemini
COFFER_LLM_PROVIDER=gemini
COFFER_GEMINI_API_KEY=<klucz z Google AI Studio>
COFFER_GEMINI_MODEL=gemini-3.5-flash-lite

# albo OpenAI / API zgodne z OpenAI
COFFER_LLM_PROVIDER=openai
COFFER_OPENAI_API_KEY=<klucz>
COFFER_OPENAI_MODEL=gpt-4o-mini
COFFER_OPENAI_BASE_URL=https://api.openai.com/v1

# albo Anthropic Claude
COFFER_LLM_PROVIDER=anthropic
COFFER_ANTHROPIC_API_KEY=<klucz z console.anthropic.com>
COFFER_ANTHROPIC_MODEL=claude-sonnet-5-5
```

**Klucz do Claude.** Załóż konto na [console.anthropic.com](https://console.anthropic.com), w *Settings → Billing* doładuj kredyty (API jest płatne z góry; bez kredytów każde wywołanie kończy się błędem i asystent pokazuje „asystent niedostępny”), potem w *Settings → API Keys* kliknij *Create Key* i wklej klucz (`sk-ant-...`) do `COFFER_ANTHROPIC_API_KEY`. Model można zmienić w `COFFER_ANTHROPIC_MODEL` (np. tańszy `claude-haiku-5-5` albo mocniejszy `claude-opus-5-5`).

Bez klucza status asystenta to „Model niedostępny”, a reszta aplikacji działa normalnie. Klucze są czytane tylko z konfiguracji: nie trafiają do logów, komunikatów błędów ani odpowiedzi API (pola mają `repr=False`, Gemini dostaje klucz w nagłówku `x-goog-api-key`, a nie w URL, Claude w nagłówku `x-api-key`).

**Implementacja** ([`src/backend/coffer/agent/llm.py`](../src/backend/coffer/agent/llm.py), tylko `httpx`, bez SDK dostawców):
- Wszyscy dostawcy implementują ten sam `Protocol` `LLMClient`: `status()` i `complete(system, messages, response_schema)` zwracające `LLMResponse` (treść, model, tokeny wejścia/wyjścia). Reszta agenta nie wie, z którym dostawcą rozmawia; klienta wybiera fabryka `get_llm_client()` na podstawie `COFFER_LLM_PROVIDER` (`none` → brak klienta).
- **Structured output** (schemat JSON szkicu sugestii):
  - Ollama: pole `format` z całym schematem;
  - OpenAI: Chat Completions (`POST {base_url}/chat/completions`) z `response_format: {type: "json_schema", json_schema: {name, schema, strict: false}}` (tryb nieścisły, bo schematy Pydantic nie mają `additionalProperties: false`; i tak waliduje je nasz walidator);
  - Gemini: `generateContent` z `systemInstruction` i `generationConfig.responseMimeType = "application/json"` + `responseSchema`. Gemini przyjmuje tylko podzbiór JSON Schema, więc `gemini_schema()` rozwija `$ref`/`$defs`, zamienia `anyOf [T, null]` i `type: [T, null]` na `nullable: true` oraz usuwa nieobsługiwane słowa kluczowe (`additionalProperties`, `title`, `default` itd.). Role `assistant` mapowane są na `model`.
  - Claude: Messages API (`POST {base_url}/v1/messages`, nagłówki `x-api-key` i `anthropic-version: 2026-10-21`), prompt systemowy w osobnym polu `system`, `max_tokens` 16000. Schemat idzie w `output_config.format = {type: "json_schema", schema}` (structured outputs; wymuszone narzędzie przez `tool_choice` nie działa na najnowszych modelach). API wymaga `additionalProperties: false` w każdym obiekcie i nie przyjmuje ograniczeń liczbowych/długości, więc `anthropic_schema()` dopisuje to pierwsze i usuwa drugie. Z odpowiedzi brane są tylko bloki `text`; `stop_reason` `refusal` lub `max_tokens` → `LLMUnavailable`. Dla modeli, które to wspierają (np. `claude-sonnet-5-5`), włączony jest serwerowy fallback przy odmowie (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`).
- **Tokeny:** OpenAI `usage.prompt_tokens`/`completion_tokens`, Gemini `usageMetadata.promptTokenCount`/`candidatesTokenCount`, Claude `usage.input_tokens`/`output_tokens`; zapisywane w śladzie przebiegu.
- **Obsługa błędów:** błąd sieci, timeout (`COFFER_LLM_TIMEOUT_S`), status HTTP ≠ 200 (np. 401 zły klucz, 429 limit) i niepoprawna/pusta odpowiedź zamieniane są na `LLMUnavailable`. `status()` dostawców chmurowych nie wykonuje płatnych wywołań: sprawdza tylko, czy skonfigurowano klucz.
- **Fallback:** przy `LLMUnavailable` workflow od razu kończy przebieg komunikatem „asystent niedostępny” (komunikat błędu nie zawiera klucza ani treści odpowiedzi), a przy nadwyżce <= 0 odpowiedź powstaje bez modelu. Rdzeń (konta, transakcje, analityka) nigdy nie zależy od LLM.

**Co trafia do modelu.** Tak samo jak przy Ollamie: tylko agregaty (przychody, wydatki, kategorie z udziałami, nadwyżka, profil inwestycyjny) i prompt systemowy. Nie trafiają e-mail, opisy transakcji ani identyfikatory. Uwaga: przy Gemini/OpenAI/Claude te agregaty opuszczają komputer i są przetwarzane przez zewnętrznego dostawcę zgodnie z jego regulaminem.

## 5. Najczęstsze problemy

| Objaw | Rozwiązanie |
|---|---|
| `make db-up` kończy się błędem, Docker nie działa | uruchom Docker Desktop, poczekaj na ikonę „running”, powtórz |
| „port is already allocated” / „address already in use” | zwolnij port (5432, 8000, 5173) albo zatrzymaj inny Postgres/serwer; `lsof -i :5432` pokaże proces |
| status „Model niedostępny” | uruchom Ollamę (`ollama serve` albo aplikację), sprawdź `ollama list`, w razie braku `ollama pull qwen3:8b`; sprawdź `COFFER_OLLAMA_URL` i nazwę modelu |
| odpowiedź modelu trwa długo | pierwsze wywołanie ładuje model do pamięci; na słabszym sprzęcie użyj `qwen3:4b` lub zwiększ `COFFER_LLM_TIMEOUT_S` |
| chcę zacząć od czystej bazy | `make db-down`, usuń wolumen (`docker volume ls`, potem `docker volume rm <projekt>_coffer-db`; albo od razu `docker compose down -v`), następnie `make db-up`, `make migrate`, `make seed` |

## 6. Jak to działa

```text
przeglądarka ──► Vite (:5173, proxy /api) ──► FastAPI (:8000) ──┬─► PostgreSQL (:5432)
                                                                 └─► Ollama (:11434, lokalny LLM)
```

**Rdzeń liczy, agent interpretuje.** Sumy, nadwyżki i udziały liczy wyłącznie `coffer.analytics` (czyste funkcje, `Decimal`). Model nigdy nie liczy: dostaje gotowe agregaty i opisuje je słowami. Brak modelu nie psuje rdzenia.

**Sugestia nadwyżki (szczegóły: [`docs/plan.md`](plan.md), sekcja 4):**
1. Kod woła narzędzia: analiza miesiąca i profil inwestycyjny (`user_id` pochodzi z sesji).
2. Gdy nadwyżka <= 0, odpowiedź powstaje bez modelu.
3. Model dostaje tylko agregaty (prompt [`agent/prompts/surplus_v2.md`](../src/backend/coffer/agent/prompts/surplus_v2.md)) i zwraca ustrukturyzowany szkic (podsumowanie, uzasadnienie, ryzyka).
4. Walidator sprawdza, czy uzasadnienie istnieje, a liczby pochodzą z wyników narzędzi.
5. Przy błędzie następuje jedna poprawka z informacją o błędzie; potem komunikat „asystent niedostępny”.
6. Sugestia i ślad przebiegu (prompty, narzędzia, wynik) są zapisywane w bazie.
7. Postęp i wynik płyną do przeglądarki przez SSE (`POST /api/agent/surplus/stream`).

**Deduplikacja importu.** Transakcja to duplikat, gdy istnieje już taka sama trójka: data + kwota + opis ze znormalizowanymi spacjami. Porównanie jest na multizbiorze: dwie identyczne transakcje w pliku przy jednej w bazie dają jedną nową i jednego duplikata.

**Prywatność.** Do modelu trafiają tylko agregaty (przychody, wydatki, kategorie z udziałami, nadwyżka, profil inwestycyjny). Nie trafiają: e-mail, opisy transakcji, identyfikatory. Przy Ollamie model działa lokalnie i dane nie opuszczają komputera; przy Gemini/OpenAI agregaty są wysyłane do dostawcy.

## 7. Struktura kodu

```text
coffer/
├── docs/             specyfikacja, plan, karty zadań
├── data/fixtures/    wymyślone dane testowe (np. [csv/testbank-2026-10.csv](../data/fixtures/csv/testbank-2026-10.csv))
├── docker/           init bazy Postgres (baza testowa)
├── .claude/          role agentów, procedura run-task, ustawienia
├── compose.yaml      Postgres 16
├── Makefile          komendy projektu
└── src/
    ├── backend/      Python 3.12, FastAPI, SQLAlchemy, Alembic
    │   ├── alembic/  migracje bazy
    │   ├── tests/    testy (podkatalog na moduł)
    │   └── coffer/
    │       ├── main.py        aplikacja FastAPI, /api/health
    │       ├── core/          konfiguracja, baza, pieniądze (quantize), miesiące, sprawdzanie origin
    │       ├── accounts/      rejestracja, logowanie, sesje, zależność CurrentUser
    │       ├── transactions/  transakcje i kategorie
    │       ├── imports/       import CSV: parser, banki, kategoryzacja, deduplikacja
    │       ├── budget/        widok miesiąca (łączy transakcje z analityką)
    │       ├── analytics/     czyste funkcje liczące sumy i udziały
    │       ├── profile/       profil inwestycyjny
    │       ├── portfolio/     portfel inwestycyjny (pozycje, wycena)
    │       ├── market/        dane rynkowe (Yahoo Finance), serwer MCP
    │       ├── agent/         asystent AI
    │       │   ├── investment/  doradca portfela (top 3, porady ze źródłami)
    │       │   ├── tools/       rejestr i narzędzia odczytu danych
    │       │   ├── workflows/   przebieg sugestii nadwyżki
    │       │   └── prompts/     wersjonowane prompty (surplus_v1, surplus_v2)
    │       └── scripts/       dump_openapi, seed_demo
    └── frontend/     React, TypeScript, Vite
        └── src/
            ├── features/    auth, transactions, import, budget, profile, portfolio, assistant
            ├── components/  wspólne komponenty; ui/ to prymitywy interfejsu
            ├── api/         klient HTTP i typy wygenerowane z OpenAPI
            ├── lib/         pomocnicze: pieniądze, miesiące, błędy, react-query
            └── i18n/        teksty interfejsu po polsku (pl.ts)
```

Pliki w `agent/`: `llm.py` (klienci LLM: Ollama, OpenAI, Gemini, Claude), `validator.py`, `anonymize.py`, `drafts.py`, `sse.py`, `api.py`, `service.py`.

**Zasady modułów:** moduł `coffer/<moduł>/` ma `api.py` (cienki router), `service.py`, `models.py`, `schemas.py`. Inne moduły korzystają z niego tylko przez `service.py` (analityka: publiczne dataclassy). Rdzeń nigdy nie importuje `coffer.agent`; pilnuje tego `import-linter` w `make lint`.

## 8. Testy i jakość

| Komenda | Co robi |
|---|---|
| `make check` | całość: lint, testy backendu, sprawdzenie frontu |
| `make lint` | ruff, pyright, import-linter |
| `make test-backend ARGS="tests/accounts"` | testy backendu (całość bez `ARGS`) |
| `make check-web` | tsc, vitest i build frontendu |
| `make openapi` | zrzut OpenAPI i typy TypeScript |

Testy backendu są w `src/backend/tests/<moduł>`, testy frontu obok kodu (`*.test.ts(x)`). Testy używają osobnej bazy (domyślnie `coffer_test`); żeby równoległe uruchomienia nie kasowały sobie danych, ustaw `COFFER_TEST_DB=coffer_test_<moduł>`.

## 9. Praca z agentami AI

Projekt jest przygotowany do pracy z agentami Claude Code. Każde zadanie ma kartę w [`docs/tasks/`](tasks/README.md) z kontraktem, listą plików i kryteriami akceptacji. Role (`implementer`, `tester`, `reviewer`, `spec-writer`) mają rozłączne pliki, a tester pisze testy niezależnie od implementacji. Krótki kontekst dla agentów jest w [`CLAUDE.md`](../CLAUDE.md). Szczegóły: [`docs/agents.md`](agents.md) i [`docs/tasks/`](tasks/README.md).
