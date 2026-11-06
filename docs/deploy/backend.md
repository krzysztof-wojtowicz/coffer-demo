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
| `COFFER_ALLOWED_ORIGINS` | sekret / ręcznie | Lista JSON z domeną frontendu, np. `["https://coffer.vercel.app"]`. Żądania POST/PUT/PATCH/DELETE z innym nagłówkiem `Origin` dostają 403. Dodaj też domeny podglądów Vercel, jeśli ich używacie. |
| `COFFER_COOKIE_SECURE` | `true` | Ustawione w Blueprincie. |
| `COFFER_LLM_PROVIDER` | `gemini` | Albo `openai` lub `none` (rdzeń działa bez LLM). Ollama nie działa na darmowym hostingu. |
| `COFFER_GEMINI_API_KEY` | sekret | Gdy provider = `gemini`. |
| `COFFER_OPENAI_API_KEY` | sekret | Gdy provider = `openai` (pole można zostawić puste). |
| `COFFER_AGENT_DAILY_LIMIT` | `20` | Limit uruchomień agenta na użytkownika na dzień (płatne API). |

Aplikacja nie ma osobnego sekretu sesji (tokeny sesji są losowe i trzymane w bazie), więc nic nie jest generowane.

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
