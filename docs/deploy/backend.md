# Wdrożenie backendu (Render, free plan)

API FastAPI działa jako **Web Service** na [Render](https://render.com) (plan free, Docker, region Frankfurt).
Konfiguracja jest w repo: `render.yaml` (Blueprint), `src/backend/Dockerfile`, `src/backend/.dockerignore`.

Architektura:

```
przeglądarka ──► Vercel (frontend, rewrite /api/*) ──► https://coffer-api-p9ku.onrender.com ──► Neon (Postgres)
```

Przeglądarka widzi jedną domenę (Vercel), więc ciasteczko sesji `SameSite=Lax` działa bez CORS.
TLS kończy się na proxy Rendera; uvicorn startuje z `--proxy-headers --forwarded-allow-ips='*'`,
a `COFFER_COOKIE_SECURE=true` nadaje ciasteczku flagę `Secure`.

## Co robi kontener przy starcie

```
alembic upgrade head && uvicorn coffer.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```

Migracje uruchamiają się przy każdym wdrożeniu (są idempotentne). Render podaje `PORT` sam.
Obraz: `python:3.12-slim` + `uv sync --frozen --no-dev` (z `uv.lock`), użytkownik nie-root `coffer`.

## Zmienne środowiskowe

| Zmienna | Wartość | Uwagi |
|---|---|---|
| `COFFER_DATABASE_URL` | sekret | URL z Neon wklejony bez zmian (`postgresql://...?sslmode=require`); aplikacja sama zamienia schemat na `postgresql+psycopg://` (zob. `docs/deploy/database.md`). |
| `COFFER_ALLOWED_ORIGINS` | sekret / ręcznie | Lista JSON z domeną frontendu, np. `["https://cofferai.vercel.app"]`. Żądania POST/PUT/PATCH/DELETE z innym nagłówkiem `Origin` dostają 403. Dodaj też domeny podglądów Vercel, jeśli ich używacie. Przyjmuje też listę po przecinku; wpis z `/` na końcu, ścieżką lub bez schematu zatrzymuje start aplikacji z czytelnym błędem. |
| `COFFER_ALLOWED_ORIGIN_REGEX` | opcjonalnie | Wzorzec dla podglądów Vercel (zob. „CORS i Origin”). |
| `COFFER_CORS_ENABLED` | `false` | CORS tylko dla bezpośrednich wywołań API z innej domeny. |
| `COFFER_COOKIE_SECURE` | `true` | Ustawione w Blueprincie. |
| `COFFER_COOKIE_SAMESITE` | `lax` | `none` tylko dla scenariusza cross-site (wymaga `COFFER_COOKIE_SECURE=true`). |
| `COFFER_LLM_PROVIDER` | `gemini` | Albo `openai` lub `none` (rdzeń działa bez LLM). Także `anthropic` albo `ollama` (tylko zdalna). Szczegóły: „AI/LLM na produkcji”. |
| `COFFER_LLM_FALLBACKS` | `gemini:gemini-3.8-flash` | Łańcuch zapasowych modeli `provider:model` po przecinku. |
| `COFFER_LLM_TIMEOUT_S` | `40` | Budżet czasu na jedno wywołanie modelu łącznie z ponowieniami. |
| `COFFER_ADVISOR_TIMEOUT_S` | `60` | Łączny budżet czasu doradcy inwestycyjnego (wszystkie kroki); musi być < 110. |
| `COFFER_GEMINI_API_KEY` | sekret | Gdy provider = `gemini`. |
| `COFFER_OPENAI_API_KEY` | sekret | Gdy provider = `openai` (pole można zostawić puste). |
| `COFFER_AGENT_DAILY_LIMIT` | `20` | Limit uruchomień agenta na użytkownika na dzień (płatne API). |

Aplikacja nie ma osobnego sekretu sesji (tokeny sesji są losowe i trzymane w bazie), więc nic nie jest generowane.

## AI/LLM na produkcji

Asystent (nadwyżka, strumień SSE) i doradca inwestycyjny wołają model przez `coffer/agent/llm.py`. Brak modelu nie psuje rdzenia: nadwyżka pokazuje samo podsumowanie, doradca zwraca propozycje regułowe (`llm_used=false`).

**Odporność.** Każde wywołanie ma budżet `COFFER_LLM_TIMEOUT_S` (z ponowieniami). Statusy 429/500/502/503/504 oraz błędy sieci i timeouty są ponawiane maks. 2 razy z wykładniczym backoffem z jitterem (1 s, 2 s, …), z poszanowaniem `Retry-After`; ponowienie, które nie zmieści się w budżecie, jest pomijane. 400/401/403/404 nie są ponawiane. Gdy model nadal jest niedostępny, aplikacja przechodzi do następnego wpisu z `COFFER_LLM_FALLBACKS` (pierwszy jest zawsze `COFFER_LLM_PROVIDER` + jego `*_MODEL`; duplikat jest pomijany). Strumień SSE wysyła od razu komentarz `: ping` i powtarza go co 15 s, więc proxy Vercel (120 s do pierwszego bajtu) nie zrywa połączenia. `COFFER_LLM_TIMEOUT_S=40` trzyma pojedyncze wywołanie wyraźnie poniżej tego limitu. Doradca inwestycyjny (zwykłe żądanie JSON, do 4 kroków) ma łączny budżet `COFFER_ADVISOR_TIMEOUT_S` (domyślnie 60 s, walidacja < 110): każde wywołanie modelu dostaje min(własny timeout, pozostały czas), a po wyczerpaniu budżetu doradca zwraca propozycje regułowe z `llm_used=false` i `ai_status: "timeout"` (przebieg w `agent_runs` ze statusem `timeout`); UI pokazuje wtedy komunikat „Model AI nie odpowiedział na czas…”.

**Przełączenie dostawcy (Render → serwis `coffer-api` → Environment):** zmień zmienne i kliknij *Save, rebuild and deploy* (albo *Save and deploy*; zmiana env wymaga restartu).

| Dostawca | Ustaw |
|---|---|
| Gemini (domyślnie) | `COFFER_LLM_PROVIDER=gemini`, `COFFER_GEMINI_API_KEY` (Google AI Studio), `COFFER_GEMINI_MODEL=gemini-3.5-flash-lite` (stabilny, zweryfikowany na żywo), `COFFER_LLM_FALLBACKS=gemini:gemini-3.8-flash` |
| Anthropic | `COFFER_LLM_PROVIDER=anthropic`, `COFFER_ANTHROPIC_API_KEY`, `COFFER_ANTHROPIC_MODEL` (np. `claude-haiku-5-5`); jako zapas za Gemini: dopisz `anthropic:claude-haiku-5-5` do `COFFER_LLM_FALLBACKS` i ustaw klucz |
| OpenAI / API zgodne | `COFFER_LLM_PROVIDER=openai`, `COFFER_OPENAI_API_KEY`, `COFFER_OPENAI_MODEL`, `COFFER_OPENAI_BASE_URL` |
| Ollama zdalna | `COFFER_LLM_PROVIDER=ollama`, `COFFER_OLLAMA_URL`, `COFFER_OLLAMA_MODEL`, `COFFER_OLLAMA_API_KEY` (gdy endpoint wymaga klucza) |
| Wyłączenie AI | `COFFER_LLM_PROVIDER=none` |

**Ollama w hostingu.** Ollama z modelem (np. `qwen3:8b`, ~5 GB) nie zmieści się na Render free (512 MB RAM, bez GPU). Opcje:
1. **Ollama Cloud** (hostowane modele Ollamy): `COFFER_OLLAMA_URL=https://ollama.com`, klucz z ollama.com → *Settings → Keys* w `COFFER_OLLAMA_API_KEY` (wysyłany jako `Authorization: Bearer`), model z listy chmurowej (np. `gpt-oss:120b`; `GET /api/tags` pokazuje dostępne). Najprostsza opcja, ten sam protokół co lokalnie.
2. **Własny komputer z GPU przez tunel** (Cloudflare Tunnel `cloudflared tunnel --url http://localhost:11434` albo ngrok): `COFFER_OLLAMA_URL=https://<tunel>`. Ollama nie ma własnego uwierzytelniania, więc tunel trzeba zabezpieczyć (Cloudflare Access z service tokenem, reverse proxy sprawdzające `Authorization: Bearer <klucz>`); bez tego każdy zna adres = darmowy model dla świata. Działa tylko, gdy komputer jest włączony; adresy „quick tunnel” zmieniają się przy restarcie.
3. **Wynajęty host GPU** (RunPod, Vast.ai, Modal, Fly GPU) z Ollamą za reverse proxy z kluczem; koszt za godzinę pracy, sensowny tylko na czas prezentacji.

Lokalnie nic się nie zmienia: pusty `COFFER_OLLAMA_API_KEY` = brak nagłówka.

**Sprawdzenie:** po zalogowaniu `GET https://cofferai.vercel.app/api/agent/status` → `{"provider": "gemini", "model": "...", "available": true}`. Przy łańcuchu pokazuje pierwszy dostępny model (aktywny). Status sprawdza tylko metadane modelu (bez kosztu, cache 60 s, nie jest wykonywany przy starcie, więc cold start go nie blokuje), więc `available: true` nie gwarantuje, że generowanie działa: przebiegi w *Asystent → Przebiegi agenta* (`/api/agent/runs`) pokazują faktyczny model, status i błąd.

**Typowe błędy** (log Render: `LLM gemini/<model> unavailable (...)`, przebieg agenta: pole `error`):
- `status 404`: model niedostępny dla klucza (stare `gemini-2.x` dla nowych kluczy zwracają 404 przy generowaniu, choć metadane odpowiadają) → zmień `COFFER_GEMINI_MODEL` lub łańcuch.
- `status 503` / `ReadTimeout`: przeciążenie („high demand”, częste dla `gemini-3.8-flash`) → ponowienia + fallback; dlatego model główny to `gemini-3.5-flash-lite`, a `3.8-flash` jest tylko w łańcuchu.
- `status 401`/`403`: zły lub nieaktywny klucz (Anthropic: brak kredytów) → popraw sekret.
- `status 429`: limit dostawcy (RPM/dzienny limit darmowego klucza) → fallback na innego dostawcę.
- Asystent: „Osiągnięto dzienny limit…”, doradca: `ai_status: "limited"` → wyczerpany `COFFER_AGENT_DAILY_LIMIT` (wspólny dla nadwyżki i doradcy, liczony od północy UTC; zapisy w `agent_runs`).

## CORS i Origin

Polityka originów jest jedna (`coffer/core/origin.py`, funkcja `is_allowed_origin`): origin jest zaufany, gdy jest dokładnie na liście `COFFER_ALLOWED_ORIGINS` albo w całości pasuje do `COFFER_ALLOWED_ORIGIN_REGEX` (`re.fullmatch`). Z tej samej decyzji korzystają oba mechanizmy, więc nie da się ich rozjechać:

- **Kontrola Origin (ochrona CSRF, zawsze włączona):** POST/PUT/PATCH/DELETE z nagłówkiem `Origin` spoza polityki dostaje 403. Żądania bez `Origin` (curl, GET z tej samej domeny) i metody bezpieczne, w tym `OPTIONS`, przechodzą bez zmian.
- **CORS (`COFFER_CORS_ENABLED=true`, domyślnie wyłączony):** `CORSMiddleware` Starlette z `allow_credentials=True`, tylko jawne originy (nigdy `*`), metody GET/POST/PUT/PATCH/DELETE, nagłówek `Content-Type` (plus nagłówki „safelisted”, np. `Accept: text/event-stream` dla SSE), `max_age=600` s dla preflightu. CORS jest najbardziej zewnętrzną warstwą, więc preflight `OPTIONS` jest obsłużony przed kontrolą Origin i przed logowaniem (nigdy 401/403), a nagłówki CORS trafiają też do odpowiedzi błędów i strumienia SSE asystenta.

**Kiedy CORS jest potrzebny.** W obecnym wdrożeniu nie: przeglądarka rozmawia z domeną Vercel, a `vercel.json` przepisuje `/api/*` na Render. Dotyczy to także podglądów Vercel (każdy deployment ma ten sam rewrite) i lokalnego `npm run dev` (proxy Vite na `localhost:8000`). Uwaga: Vercel przekazuje nagłówek `Origin` przeglądarki, więc domeny podglądów i tak muszą przejść kontrolę Origin; do tego wystarczy `COFFER_ALLOWED_ORIGIN_REGEX`, bez włączania CORS. CORS jest potrzebny dopiero, gdy front woła `https://coffer-api-p9ku.onrender.com` bezpośrednio (wymaga to w froncie bazowego URL API, którego dziś nie ma: wszystkie wywołania są względne, `/api/...`).

**Podglądy Vercel:**

```
COFFER_ALLOWED_ORIGINS=["https://cofferai.vercel.app"]
COFFER_ALLOWED_ORIGIN_REGEX=https://cofferai-[a-z0-9-]+-<team-slug>\.vercel\.app
```

Wzorzec jest dopasowywany w całości (`re.fullmatch`), a `^` i `$` na brzegach są opcjonalne (aplikacja je usuwa). Przy starcie sprawdzana jest jego bezpieczna postać, a każdy inny wzorzec kończy się czytelnym błędem:
- `https://` + host zaczynający się od dosłownego znaku (np. `cofferai-`), w środku tylko litery, cyfry i `-` albo klasy `[a-z0-9-]`/`\d` z kwantyfikatorem (`+`, `*`, `?`, `{n,m}`), na końcu co najmniej dwa dosłowne labele z escapowanymi kropkami (`\.vercel\.app`), opcjonalnie port (`:8443`, `:\d+`, `(:\d+)?`);
- albo dokładnie `http://localhost` / `http://127\.0\.0\.1` z opcjonalnym portem jak wyżej;
- zakazane: `.`, `.*`, `.+` i `\w` w hoście, alternacja `|`, grupy, `[^...]`, `https?://`, wielkie litery.

Odrzucane są więc np. `https://.*`, `https://coffer\.app|.*`, `http://localhost.*`. Walidator nie zna Public Suffix List: wzorzec kończący się sufiksem publicznym (np. `\.co\.uk`) przejdzie, ale wpuści cudze domeny.

**Lokalny front wskazujący na API (bez proxy Vite):** `COFFER_CORS_ENABLED=true`, `COFFER_ALLOWED_ORIGINS=http://localhost:5173`. Na tym samym hoście (`localhost:5173` → `localhost:8000`) żądanie jest cross-origin, ale same-site, więc `SameSite=Lax` wystarcza.

**Ciasteczko przy cross-site.** `vercel.app` i `onrender.com` są na Public Suffix List, więc front na `*.vercel.app` wołający bezpośrednio Render jest cross-site: ciasteczko `SameSite=Lax` nie zostanie wysłane w `fetch`. Działałoby tylko z `COFFER_COOKIE_SAMESITE=none` (+ `COFFER_COOKIE_SECURE=true`, walidowane przy starcie). Trade-off: przy `none` ciasteczko leci w każdym żądaniu cross-site, więc jedyną ochroną CSRF zostaje kontrola Origin (przeglądarki wysyłają `Origin` przy cross-site POST, ale żądanie bez `Origin` przechodzi). Do tego Safari i przeglądarki blokujące ciasteczka stron trzecich i tak je odrzucą. Zalecenie: zostać przy rewrite Vercel i `lax`; `none` tylko świadomie i tymczasowo.

**Ostrzeżenia:**
- Każdy origin z listy lub pasujący do regexu może przy `none` czytać dane zalogowanego użytkownika. Regex na współdzielonej domenie (`vercel.app`) jest słabszy od listy: obcy projekt nazwany np. `coffer-x-<team-slug>` dostałby adres pasujący do wzorca. Trzymaj wzorzec możliwie wąski i preferuj dokładne originy.
- Wpis w `COFFER_ALLOWED_ORIGINS` to dokładnie `schemat://host[:port]` małymi literami, bez `/` na końcu; inaczej aplikacja nie wystartuje.
- Własna domena (np. `app.coffer.pl` + `api.coffer.pl`) jest same-site, więc wystarczy `lax` + CORS z tym originem.

## Pierwsze wdrożenie krok po kroku

1. Wejdź na <https://dashboard.render.com> i zaloguj się przez **GitHub** (Sign in with GitHub). Karta płatnicza nie jest potrzebna dla planu free.
2. Daj Renderowi dostęp do repozytorium Coffer (przy pierwszym logowaniu albo w *Account Settings → GitHub → Configure*).
3. **New → Blueprint**, wybierz repo i gałąź `main`. Render znajdzie `render.yaml` i pokaże serwis `coffer-api`.
4. Uzupełnij pola oznaczone jako sekrety (`sync: false`): `COFFER_DATABASE_URL` (od osoby od Neon), `COFFER_ALLOWED_ORIGINS` (domena z Vercel), `COFFER_GEMINI_API_KEY` (lub `COFFER_OPENAI_API_KEY`). Kliknij **Apply**.
5. Render zbuduje obraz i uruchomi serwis. Pierwszy build trwa kilka minut.
6. Sprawdź: `curl https://coffer-api-p9ku.onrender.com/api/health` → `{"status":"ok"}`.
   Jeśli nazwa `coffer-api` była zajęta, Render doda sufiks (np. `coffer-api-x1y2.onrender.com`): przekaż nowy URL osobie od frontendu (rewrite w Vercel).
7. Dane demo (opcjonalnie): lokalnie `COFFER_DATABASE_URL=<url z Neon> make seed`.

Zmiana zmiennych: serwis → **Environment** → edycja → *Save, rebuild and deploy*.

## Logi i diagnostyka

- Serwis → **Logs**: logi na żywo (build, migracje, uvicorn). **Events**: historia wdrożeń.
- Błąd `ModuleNotFoundError: psycopg2` → nie powinien wystąpić (schemat jest normalizowany w `coffer/core/db_url.py`); jeśli wystąpi, sprawdź, czy URL nie ma literówki w schemacie.
- 403 „Niedozwolone źródło żądania” przy logowaniu → domena frontendu nie jest w `COFFER_ALLOWED_ORIGINS`.
- Logowanie działa, ale sesja „znika” → frontend woła `onrender.com` bezpośrednio zamiast przez rewrite `/api/*` w Vercel.

## Usypianie na planie free

Serwis free zasypia po **15 minutach** bez ruchu; pierwsze żądanie po uśpieniu budzi go ok. 30–60 s
(frontend może w tym czasie pokazywać ładowanie). Limit to 750 godzin pracy instancji miesięcznie,
co wystarcza na jeden serwis działający cały czas.

Opcjonalnie przed prezentacją: ping co 10–14 min na `/api/health`, np. darmowy monitor
[UptimeRobot](https://uptimerobot.com) (HTTP, interwał 5–10 min) albo zadanie cron w GitHub Actions.
Nie trzymajcie serwisu wiecznie wybudzonego bez potrzeby.

## Deploy hook (GitHub Actions)

`autoDeploy` jest wyłączony: wdrożenie wyzwala GitHub Actions po przejściu testów.

1. Serwis → **Settings → Deploy Hook** → skopiuj URL (to sekret: każdy, kto go zna, może wyzwolić wdrożenie).
2. W GitHub: repo → *Settings → Secrets and variables → Actions → New repository secret*,
   nazwa **`RENDER_DEPLOY_HOOK_URL`**, wartość: skopiowany URL.
3. Workflow wywołuje go przez `curl -fsS -X POST "$RENDER_DEPLOY_HOOK_URL"`.

Do tego czasu wdrażaj ręcznie: serwis → **Manual Deploy → Deploy latest commit**.

## Test lokalny obrazu

```bash
cd src/backend
docker build -t coffer-api:local .
docker run --rm -p 8080:10000 -e PORT=10000 \
  -e COFFER_DATABASE_URL=postgresql+psycopg://coffer:coffer@host.docker.internal:5432/coffer \
  -e COFFER_LLM_PROVIDER=none coffer-api:local
curl localhost:8080/api/health
```
