# Frontend: Vercel (Hobby plan)

The frontend (`src/frontend`, React + Vite) is a static build in `dist/` hosted free on Vercel. The backend runs on Render ([backend.md](backend.md)).

## How it works
The app calls the API with relative paths (`/api/...`), and the session is an `HttpOnly`, `SameSite=Lax` cookie without a `Domain`, so the browser must see the API on the **same domain**. `src/frontend/vercel.json` does this:
- **Rewrites:** `/api/:path*` → `https://coffer-api-p9ku.onrender.com/api/:path*` (Vercel acts as a reverse proxy, passing `Cookie`/`Set-Cookie` through unchanged); every other path → `/index.html` (SPA fallback). Static files are served before rewrites.
- `x-vercel-enable-rewrite-caching: 0` on `/api/*`: API responses are never cached by the CDN.
- `/assets/*` (hashed names) cached for a year (`immutable`); `index.html` with `no-cache`.
- `buildCommand`: `npx tsc --noEmit -p tsconfig.app.json && npx vite build` (same as `make check-web`). Not `npm run build`, because `tsc -b` also checks `vite.config.ts`, which fails type-checking (`vitest` bundles its own `vite`).
- The build needs neither the backend nor `openapi.json`: API types are in the committed `src/api/schema.d.ts`. After an API change, run `make openapi` and commit it.

To point at another backend URL, change the `destination` of the first rewrite (keep `/api/:path*`) and push; `vercel.json` doesn't read env variables.

## SSE limits
`POST /api/agent/actions/{id}/run` with `Accept: text/event-stream` streams through the rewrite. Limits (Hobby and Pro alike):
- **120 s to the first byte**, otherwise `ROUTER_EXTERNAL_TARGET_ERROR` (502/504). After the first byte the stream may continue as long as something arrives every 120 s; the backend sends `: ping` every 15 s.
- **Render Free cold start** (~30–60 s after 15 min idle) fits within 120 s, but the first login is slow. Wake `/api/health` before a demo.

## Setup
1. <https://vercel.com/signup> → **Hobby** → **Continue with GitHub**, grant access to the repo (an org owner may need to approve).
2. **Add New → Project → Import** the repo.
3. **Root Directory: `src/frontend`** (the key setting; `vercel.json` is read from there). Framework, build, output and install settings come from `vercel.json`. No env variables are needed.
4. **Deploy**. Every push to `main` deploys production; every PR gets a preview URL using the same backend.
5. On Render set `COFFER_COOKIE_SECURE=true`. No CORS needed.
6. Custom domain (optional): **Settings → Domains → Add**, then the `CNAME`/`A` record Vercel shows. No code changes.

**After deploying:** `/api/health` returns backend JSON (not HTML); you can register and log in; the cookie is for `<project>.vercel.app` with `HttpOnly; Secure; SameSite=Lax`; refreshing `/transactions` loads the app (no 404); assistant output streams; logout makes `/api/auth/me` return 401.

## Security headers
`vercel.json` adds to every response:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`

The strict CSP works because the Vite build has no inline scripts or styles, loads no external fonts or CDNs, and all API calls are relative. If you add an external resource, extend the matching directive. On previews the CSP blocks the Vercel Toolbar. Check with:
```bash
curl -sI https://cofferai.vercel.app/ | grep -iE 'x-frame|content-security|x-content|referrer|permissions'
```

## Alternatives
- **Netlify:** base `src/frontend`, build `npx vite build`, publish `dist`, `public/_redirects` with `/api/* https://coffer-api-p9ku.onrender.com/api/:splat 200` and `/* /index.html 200`. Its proxy timeout (~26 s) copes worse with Render cold starts.
- **Cloudflare Pages:** `_redirects` can't proxy to external domains; `/api/*` needs a small Pages Function that `fetch`es Render.
