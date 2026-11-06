# Checklista wdrożenia: gałąź `feat/auth-cors-datamodel`

Zakres: migracja `0005_accounts`, nowa polityka haseł i rate limit logowania, Argon2id (m=19 MiB),
nowe endpointy `/api/auth/{password,account,logout-all}`, wspólna polityka Origin/CORS, nagłówki
bezpieczeństwa w `vercel.json`, nowe hasło demo. Stan produkcji przed wdrożeniem (2026-11-06):
Neon `dark-hall-98925715`, gałąź `production`, migracja `0004`; sekret `RENDER_DEPLOY_HOOK_URL`
**nie jest ustawiony** (deploy.yml tylko się pomija), więc backend wdrażasz ręcznie w Render.

Dochodzi też odporność LLM: łańcuch fallbacków, budżet czasu na wywołanie, `ai_status` doradcy,
`GET /api/agent/status`. Agent LLM nie zmienia schematu bazy (jedyna migracja to `0005`).

## 0. Przed merge (lokalnie / CI)

Stan z 2026-11-06 na końcowym diffie: `make lint` OK; `make check` OK (backend 755 passed + 5 xfailed,
front 150 testów, build); OpenAPI zgodne; `alembic check` bez dryfu; `docker build` OK.

- [ ] Powtórz `make check` po ostatnich poprawkach (`COFFER_ADVISOR_TIMEOUT_S`).
- [ ] `make openapi` nie zmienia `src/frontend/src/api/schema.d.ts`.
- [ ] Workflow „Migrations” na PR zielony (jedna głowa, `alembic check`, downgrade/upgrade).
  Lokalnie sprawdzone: `upgrade head`, `check`, `downgrade 0004`, `upgrade head` OK.

## 1. Neon: sprawdzenie danych i punkt przywracania

1. W Neon Console → SQL Editor, gałąź `production` uruchom (tylko odczyt):

   ```sql
   SELECT version_num FROM alembic_version;                       -- oczekiwane: 0004
   SELECT lower(btrim(email)) AS e, count(*) FROM users
   GROUP BY 1 HAVING count(*) > 1;                                 -- oczekiwane: 0 wierszy
   SELECT count(*) FROM users WHERE email <> lower(btrim(email));  -- te adresy migracja znormalizuje
   SELECT substring(password_hash from 'm=[0-9]+,t=[0-9]+,p=[0-9]+') AS params, count(*)
   FROM users GROUP BY 1;                                          -- stare hashe (m=65536) dostaną rehash przy logowaniu
   ```

   Jeśli zapytanie o duplikaty zwróci wiersze, **nie wdrażaj**. Migracja `0005` przerwie się z
   `RuntimeError`, kontener nie wystartuje, a Render zostawi poprzednią wersję. Najpierw scal lub
   zmień ręcznie zduplikowane konta.
2. Utwórz gałąź-punkt przywracania (kopia copy-on-write, nic nie kosztuje przy ~32 MB):

   ```bash
   neon branches create --project-id dark-hall-98925715 --parent production \
     --name pre-0005-$(date +%Y%m%d)
   neon branches list --project-id dark-hall-98925715
   ```

   (Albo w konsoli: Branches → New branch → parent `production`, „Current point in time”.)

## 2. Render: zmienne środowiskowe PRZED deployem

Settings → Environment usługi `coffer-api`:

- [ ] `COFFER_ALLOWED_ORIGINS` = `["https://cofferai.vercel.app"]`, dokładnie, małymi literami, **bez `/` na końcu**.
  Nowa walidacja zatrzymuje start przy `/` na końcu, ścieżce lub wielkich literach (sprawdzone na obrazie: obecna wartość przechodzi).
- [ ] `COFFER_COOKIE_SAMESITE` = `lax`, `COFFER_CORS_ENABLED` = `false` (Blueprint ma te wartości; przy ręcznie
  utworzonej usłudze dodaj je ręcznie. Brak nie psuje startu, bo domyślne są takie same).
- [ ] `COFFER_ALLOWED_ORIGIN_REGEX`: zostaw puste, chyba że podglądy Vercel mają robić POST. Wzorzec
  **musi zaczynać się dosłownie od `https://`** (bez `^`, bez `.*`), z escapowanymi kropkami, np.
  `https://cofferai-[a-z0-9-]+-<team>\.vercel\.app`. Inaczej start aplikacji padnie.
- [ ] `COFFER_TRUSTED_PROXY_HOPS` = `0`. Nie zmieniaj, dopóki nie zweryfikujesz liczby proxy (sekcja 6).
- [ ] `COFFER_PASSWORD_HASH_CONCURRENCY` = `2` (Argon2, pamięć przy 512 MB).
- [ ] `COFFER_LLM_TIMEOUT_S` = `40` (budżet na jedno wywołanie modelu łącznie z ponowieniami; poprzednio 60).
- [ ] `COFFER_LLM_FALLBACKS` = `gemini:gemini-3.5-flash-lite`. Format `provider:model` po przecinku;
  zły wpis zatrzymuje start.
- [ ] `COFFER_GEMINI_MODEL`: test na żywo pokazał, że działa tylko `gemini-3.5-flash-lite`, a
  `gemini-3.8-flash` (wartość z Blueprintu) daje 503 albo timeout. Przy `gemini-3.8-flash` każde
  pytanie czeka do 40 s, zanim zadziała fallback. **Zalecane:** `COFFER_GEMINI_MODEL=gemini-3.5-flash-lite`
  (fallback zostaje jako zabezpieczenie).
- [ ] `COFFER_ADVISOR_TIMEOUT_S` (domyślnie 60, dozwolone 1–109): zostaw domyślne albo wartość z `render.yaml`.
  Musi być mniejsze niż limit 120 s proxy Vercel.
- [ ] `COFFER_OLLAMA_URL`, `COFFER_OLLAMA_MODEL`, `COFFER_OLLAMA_API_KEY`: opcjonalne, tylko przy
  `COFFER_LLM_PROVIDER=ollama` ze zdalną Ollamą. W przeciwnym razie nie ustawiaj.
- [ ] `COFFER_GEMINI_API_KEY` ustawiony (bez niego fallback gemini też nie zadziała, a rdzeń działa dalej).

Wartości z `render.yaml` (`value:`) trafiają do usługi tylko przy synchronizacji Blueprintu. Przy usłudze
utworzonej ręcznie ustaw je w Environment sam. Zmiana zmiennych wywołuje redeploy obecnego commitu.
To bezpieczne, bo obecny kod ignoruje nowe zmienne (`COFFER_LLM_TIMEOUT_S=40` działa od razu i w starym kodzie).

## 3. Kolejność wdrożenia

Vercel buduje `main` automatycznie po merge, a backend wdrażasz ręcznie. Przez kilka minut nowy front
działa więc ze starym API. Logowanie i rejestracja działają, a nowa strona konta (zmiana hasła, usunięcie
konta, wyloguj wszędzie) zwraca wtedy 404/405. Żeby skrócić to okno:

1. Merge PR do `main`, zaczekaj na zielone CI.
2. **Od razu** Render → Manual Deploy → „Deploy latest commit”. Build trwa kilka minut,
   potem `alembic upgrade head` (0004 → 0005, ułamek sekundy: krótka blokada zapisu w `users`
   przy `CREATE UNIQUE INDEX`, dodanie kolumn bez wartości domyślnej to tylko zmiana metadanych).
   Stara instancja obsługuje ruch do czasu, aż health check nowej przejdzie. Stary kod działa poprawnie na schemacie 0005.
3. Sprawdź log deployu: `Running upgrade 0004 -> 0005` i start uvicorn.
4. Front: Vercel wdraża sam. Jeśli chcesz zerowego okna, wstrzymaj produkcyjny deploy w Vercel
   (Deployment → nie promuj) i zrób „Promote to Production” po kroku 3.

## 4. Testy dymne po wdrożeniu

Nie zakładaj kont testowych na produkcji w ramach automatów. Poniższe klika człowiek na własnym koncie.

```bash
curl -s https://coffer-api-p9ku.onrender.com/api/health          # {"status":"ok"}
curl -s https://cofferai.vercel.app/api/health                    # {"status":"ok"} przez rewrite
curl -sI https://cofferai.vercel.app/ | grep -iE 'x-frame|content-security|x-content|referrer|permissions'
# Origin obcy -> 403 (bez danych logowania, nic nie zapisuje):
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Origin: https://evil.example' \
  -H 'Content-Type: application/json' -d '{}' https://cofferai.vercel.app/api/auth/login   # 403
# Preflight przy CORS wyłączonym -> 405 (brak nagłówków Access-Control-*):
curl -s -o /dev/null -w '%{http_code}\n' -X OPTIONS -H 'Origin: https://evil.example' \
  -H 'Access-Control-Request-Method: POST' https://coffer-api-p9ku.onrender.com/api/auth/login
```

W przeglądarce (https://cofferai.vercel.app, DevTools → Console bez błędów CSP):
- [ ] Logowanie istniejącym kontem działa; ciasteczko sesji `HttpOnly; Secure; SameSite=Lax`.
- [ ] Pulpit, transakcje, budżet, portfel ładują się; asystent (SSE) odpowiada albo pokazuje komunikat o braku LLM.
- [ ] Strona konta: zmiana hasła (słabe hasło → komunikat po polsku), „wyloguj wszędzie”.
- [ ] Status AI (zalogowany, DevTools lub karta w przeglądarce): `GET /api/agent/status` →
  `{"provider":"gemini","model":"gemini-3.5-flash-lite","available":true}`. `model` to aktywny model łańcucha.
  Bez sesji odpowiedź to 401, tak ma być.
- [ ] Doradca inwestycyjny (`POST /api/agent/investment/advice`, panel doradcy): odpowiedź w < 60 s z
  `ai_status: "ok"`. `ai_status: "limited"` (limit dzienny lub timeout) albo `"unavailable"` (brak LLM)
  też jest poprawne: część liczbowa się wyświetla, panel pokazuje komunikat po polsku, nie ma 5xx ani 504 z Vercel.
- [ ] Asystent (SSE): pierwsze pytanie po zimnym starcie kończy się odpowiedzią albo komunikatem w < 2 min.
- [ ] Render → Logs: brak tracebacków; przy 503 od modelu głównego widać przejście na fallback.
- [ ] Neon SQL Editor: `SELECT version_num FROM alembic_version;` → `0005`; po zalogowaniu hash ma `m=19456,t=2,p=1`.
- [ ] Render → Metrics: pamięć < ~350 MB po kilku logowaniach.
- [ ] Konto demo (jeśli istnieje na prod) ma stare hasło `demo12345` do czasu `make seed-remote CONFIRM=yes ...`.
  Nowe hasło: `coffer-demo-2026`.

## 5. Plan wycofania

| Co | Jak |
|---|---|
| Front | Vercel → Deployments → poprzedni produkcyjny → **Instant Rollback**. Działa ze starym i nowym API. |
| Backend, gdy migracja **nie** przeszła | Nic nie rób: deploy padł, Render dalej serwuje poprzednią wersję. Popraw dane/kod i wdroż ponownie. |
| Backend, gdy migracja przeszła | **Najpierw cofnij schemat, potem kod.** Stary obraz uruchamia `alembic upgrade head` i nie zna rewizji `0005` („Can't locate revision”), więc bez tego rollback w Render nie wystartuje. Z lokalnego checkoutu tej gałęzi: `cd src/backend && COFFER_DATABASE_URL='<url Neon production>' uv run alembic downgrade 0004`, potem Render → Events → poprzedni deploy → **Rollback**. |
| Dane | Ostateczność: przywróć `production` z gałęzi `pre-0005-*` (Neon → Branches → Restore lub reset z gałęzi). Traci zapisy od chwili jej utworzenia. |

Downgrade `0005` zostawia e-maile znormalizowane małymi literami (nieodwracalne, ale niegroźne)
i przywraca `users_email_key`. Stare hashe przepisane na nowe parametry stary kod nadal weryfikuje.

## 6. Znane ryzyka i decyzje

- **Rate limit per IP i X-Forwarded-For (niezweryfikowane).** Uvicorn z `--forwarded-allow-ips='*'`
  bierze **najbardziej lewy** wpis XFF jako `request.client.host`. Przez Vercel to (według dokumentacji
  Vercel, który nadpisuje XFF) prawdziwe IP klienta. Przy bezpośrednim wywołaniu `onrender.com`
  wartość jest podrabialna, więc limit per IP da się obejść. Limit per e-mail (10/15 min) działa zawsze.
  Za małe `COFFER_TRUSTED_PROXY_HOPS` jest groźniejsze od zbyt dużego: przy wartości wskazującej na
  IP Vercel/Cloudflare wszyscy użytkownicy dzielą jeden licznik, a 30 nieudanych logowań w 15 min
  blokuje logowanie wszystkim. Dlatego zostaje `0`, dopóki ktoś nie sprawdzi w logach Render, ile
  adresów ma nagłówek XFF przez Vercel.
- **Pamięć Argon2:** `COFFER_PASSWORD_HASH_CONCURRENCY=2`, czyli nowe hashe 2 × 19 MiB. Do czasu rehashu
  stare hashe (m=64 MiB, p=4) kosztują do 2 × 64 MiB. Bazowy proces ~90–150 MB, limit 512 MB.
- **LLM:** model główny `gemini-3.8-flash` jest niestabilny (503/timeout). Ustaw flash-lite jako główny
  (sekcja 2). Budżet 40 s na wywołanie plus timeout doradcy (domyślnie 60 s) mieszczą się w 120 s proxy Vercel.
- **Rate limit w pamięci:** reset przy restarcie i uśpieniu instancji free. Poprawny tylko przy 1 instancji i 1 workerze.
- **Podglądy Vercel:** POST z domeny podglądu dostaje 403, dopóki nie ustawisz `COFFER_ALLOWED_ORIGIN_REGEX`.
  CSP blokuje też Vercel Toolbar na podglądach.
- **Obraz:** ~1.1 GB, bez nowych zależności (`uv.lock` bez zmian); import aplikacji ~0.6 s.
