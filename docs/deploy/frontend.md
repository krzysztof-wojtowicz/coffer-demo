# Wdrożenie frontendu (Vercel, plan Hobby)

Frontend (`src/frontend`, React + Vite) to statyczny build w `dist/`. Hostujemy go za darmo na Vercel.
Backend FastAPI działa osobno na Render: `https://coffer-api-p9ku.onrender.com` (patrz instrukcja backendu).

## Jak to działa

Aplikacja woła API ścieżkami względnymi (`/api/...`), a sesja to ciasteczko `httponly`, `samesite=lax`
bez atrybutu `Domain`. Dlatego przeglądarka musi widzieć API pod **tą samą domeną** co frontend.
Załatwia to `src/frontend/vercel.json`:

- `rewrites`: `/api/:path*` → `https://coffer-api-p9ku.onrender.com/api/:path*` (Vercel działa jak reverse proxy;
  w pasku adresu zostaje domena Vercel), a każda inna ścieżka → `/index.html` (fallback SPA dla React Router).
  Pliki statyczne (`/assets/...`, `favicon.svg`) Vercel serwuje przed rewrite'ami.
- Nagłówki `Cookie` (żądanie) i `Set-Cookie` (odpowiedź) przechodzą przez zewnętrzny rewrite bez zmian.
  Ciasteczko zapisuje się dla domeny Vercel (np. `coffer.vercel.app`), bo backend nie ustawia `Domain`.
- `x-vercel-enable-rewrite-caching: 0` dla `/api/*`: CDN Vercel nigdy nie cache'uje odpowiedzi API
  (nowe projekty domyślnie honorują `Cache-Control` z originu, a dane użytkownika nie mogą trafić do cache).
- `/assets/*` (pliki z hashem w nazwie) cache'owane na rok (`immutable`), `index.html` z `no-cache`.
- `buildCommand`: `npx tsc --noEmit -p tsconfig.app.json && npx vite build` (to samo co `make check-web`).
  Nie używamy `npm run build`, bo `tsc -b` sprawdza też `vite.config.ts`, a ten obecnie nie przechodzi
  type-checku (konflikt typów: `vitest@3` ma własną kopię `vite@7`, projekt używa `vite@8`).
- Build nie potrzebuje backendu ani `openapi.json` (jest w `.gitignore`). Typy API są w
  `src/api/schema.d.ts`, który jest w repo. Po zmianie API trzeba lokalnie uruchomić `make openapi`
  i zacommitować `schema.d.ts`.

### Streaming asystenta (SSE) i ograniczenia

`POST /api/agent/surplus/stream` zwraca `text/event-stream`, a frontend czyta go przez `fetch` + `getReader()`.
Zewnętrzne rewrite'y Vercel przesyłają odpowiedź strumieniowo, więc zdarzenia docierają na bieżąco.
Ograniczenia (identyczne na Hobby i Pro):

- **Proxied request timeout: 120 s do pierwszego bajtu.** Jeśli backend nie zacznie odpowiadać w 120 s,
  Vercel zwraca błąd `ROUTER_EXTERNAL_TARGET_ERROR` (502/504). Po pierwszym bajcie strumień może trwać dłużej,
  o ile backend wysyła coś przynajmniej co 120 s.
- **Usypianie Render Free.** Pierwsze żądanie po ~15 min bezczynności budzi serwis (zwykle 30–60 s).
  Mieści się w limicie 120 s, ale pierwsze logowanie jest wolne. Obejście: przed prezentacją otworzyć
  `https://coffer-api-p9ku.onrender.com/api/health` albo ustawić darmowy ping (np. UptimeRobot co 10 min).
- **Długie przerwy między zdarzeniami SSE.** Jeśli pojedyncze wywołanie LLM trwałoby >120 s bez żadnego
  zdarzenia, proxy zerwie połączenie. Obejście (zmiana po stronie backendu, poza zakresem frontu): wysyłać
  co ~15 s komentarz SSE `: ping\n\n` (keep-alive). Ostateczność: wywoływać stream bezpośrednio pod
  `https://coffer-api-p9ku.onrender.com`, co wymaga CORS z `credentials` i ciasteczka `SameSite=None; Secure`,
  więc nie polecamy.

## Krok po kroku

### 1. Konto

1. Wejdź na <https://vercel.com/signup>, wybierz **Hobby** (darmowy, do projektów niekomercyjnych).
2. **Continue with GitHub** i zezwól Vercel na dostęp do repozytorium Coffer (wystarczy wybrane repo).
   Jeśli repo należy do organizacji, jej właściciel może musieć zatwierdzić aplikację Vercel.

### 2. Import projektu

1. Dashboard → **Add New… → Project** → przy repozytorium **Import**.
2. **Root Directory**: kliknij *Edit* i wybierz `src/frontend`. To najważniejsze ustawienie:
   Vercel czyta `vercel.json` z tego katalogu.
3. **Framework Preset**: Vite (wykryje się sam; i tak nadpisuje go `vercel.json`).
4. Build/Output/Install Command zostaw domyślne: biorą się z `vercel.json`.
5. Zmienne środowiskowe: niepotrzebne (frontend nie ma żadnych `VITE_*`).
6. **Deploy**. Po ~1 min dostaniesz adres `https://<nazwa-projektu>.vercel.app`.

Każdy push na `main` wdraża produkcję, a każdy PR dostaje własny adres podglądu (preview).
Preview też korzysta z tego samego backendu, więc logowanie działa również tam.

### 3. Backend (koordynacja z wdrożeniem Render)

- Na Render ustaw `COFFER_COOKIE_SECURE=true` (strona Vercel działa po HTTPS).
- CORS na backendzie nie jest potrzebny: przeglądarka rozmawia tylko z domeną Vercel.

### 4. Własna domena (opcjonalnie)

Project → **Settings → Domains → Add**, wpisz np. `coffer.example.pl` i dodaj u rejestratora rekord
wskazany przez Vercel (`CNAME` na `cname.vercel-dns.com` dla subdomeny albo `A` dla domeny głównej).
Certyfikat HTTPS Vercel wystawia sam. Nic w kodzie nie trzeba zmieniać.

### 5. Sprawdzenie po wdrożeniu

1. Otwórz `https://<projekt>.vercel.app/api/health`: ma zwrócić JSON z backendu (nie stronę HTML).
   Jeśli czeka długo, Render się budzi.
2. Otwórz `https://<projekt>.vercel.app/`, zarejestruj się albo zaloguj.
3. DevTools → Application → Cookies: ciasteczko sesji ma domenę `<projekt>.vercel.app`, `HttpOnly`,
   `Secure`, `SameSite=Lax`.
4. Odśwież stronę na podstronie (np. `/transactions`): ma się załadować aplikacja, a nie 404 (fallback SPA).
5. Uruchom asystenta: odpowiedź powinna pojawiać się stopniowo (DevTools → Network → typ `eventsource`/`fetch`).
6. Wyloguj się: ciasteczko znika, a `/api/auth/me` zwraca 401.

## Inny adres backendu

`vercel.json` nie czyta zmiennych środowiskowych. Jeśli backend ma inny URL, zmień `destination`
w pierwszym rewrite w `src/frontend/vercel.json` (zachowaj końcówkę `/api/:path*`), zacommituj
i wypchnij. Vercel wdroży nową wersję sam. Lokalnego dev to nie dotyczy (tam proxy jest w `vite.config.ts`).

## Alternatywy

- **Netlify**: Base directory `src/frontend`, build `npx vite build`, publish `dist`, a w `public/_redirects`
  wpisz `/api/* https://coffer-api-p9ku.onrender.com/api/:splat 200` oraz `/* /index.html 200`.
  Proxy Netlify też przekazuje ciasteczka, ale ma krótszy limit czasu (~26 s), co gorzej znosi budzenie Render.
- **Cloudflare Pages**: SPA fallback działa sam (brak `404.html`), ale `_redirects` nie proxuje do zewnętrznych
  domen. Do `/api/*` potrzebna jest mała Pages Function (`functions/api/[[path]].ts` robiąca `fetch` do Render),
  która w darmowym planie też obsługuje streaming.
