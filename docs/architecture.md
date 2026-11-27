# Coffer architecture

How Coffer is built: key decisions, stack, modules and the local runtime. The diagrams use [Mermaid](https://mermaid.js.org/) (GitHub renders them) and were drawn from the code: imports in `src/backend/coffer`, `coffer/main.py`, the `import-linter` contracts in `src/backend/pyproject.toml`, models and Alembic migrations, `src/frontend/src`, and `compose.yaml`. Behaviour is specified in [`openspec/specs/`](../openspec/specs); the data model in detail is in [data-model.md](data-model.md).

**Guiding principle: the core computes.** Every number the user sees (totals, shares, gains) comes from `coffer.analytics`, which makes exact totals (N04) true by construction.

**The AI assistant was removed** during the refactoring and will be rebuilt for local LLMs afterwards (see the [roadmap](roadmap.md)). F31–F38 and N03 are currently unimplemented.

## Contents
1. [Decisions and stack](#1-decisions-and-stack)
2. [System context](#2-system-context)
3. [Local runtime](#3-local-runtime)
4. [Backend modules and dependencies](#4-backend-modules-and-dependencies)
5. [Frontend](#5-frontend)
6. [Data model](#6-data-model)

Legend: rectangle = Coffer component; rounded `( )` = person or external client; cylinder = database; hexagon `{{ }}` = external service; solid arrow = calls/uses; dashed arrow = optional, configuration or trigger; `subgraph` = boundary.

---

## 1. Decisions and stack

| Area | Decision |
|---|---|
| App type | Web, client–server, API-first. Accounts and sessions (N02) require a server. |
| Backend | Python 3.12, FastAPI with sync `def` endpoints, Pydantic v2, SQLAlchemy 2 (sync), Alembic, psycopg 3. Sync keeps the code simple. |
| Frontend | React + TypeScript SPA (Vite), React Router, TanStack Query, Tailwind with semantic theme tokens. API types are generated from OpenAPI (`openapi-typescript` + `openapi-fetch`); regenerate them with `make openapi` after API changes. |
| Database | PostgreSQL 16: `NUMERIC` for money, `ON DELETE CASCADE` for account deletion (N09), transactions for atomic import commits, `JSONB` for document-like data (import drafts). |
| Auth | `argon2-cffi`, a session table, an HttpOnly + SameSite=Lax cookie. Deleting the session row revokes access immediately, which JWTs can't do. |
| Market data | Yahoo Finance via `yfinance`. No keys or paid services. |
| Runtime | Local development only for now: Postgres in Docker (`compose.yaml`), API and Vite dev server run natively. Vite proxies `/api/*`, so the browser sees one origin. A production deployment was removed during the refactoring (see [history.md](history.md)). |
| Quality | `uv`, `ruff`, `pyright`, `pytest`, `hypothesis`, `import-linter`; `tsc`, `vitest`. |
| Repository | Monorepo: `docs/`, `openspec/`, `src/backend/`, `src/frontend/`, `data/fixtures/`, `.claude/`. |

Rejected alternatives:
- **MongoDB.** The data is relational, and the hardest requirements are what a relational DB gives: exact decimals (N04), cascading deletes (N09), multi-row atomic import commits, and joins of per-user holdings with global quotes. `JSONB` covers the document-shaped parts.
- **Next.js.** No need for SEO or SSR, and it would add a second server next to Python.

---

## 2. System context

```mermaid
flowchart LR
    user("User<br/>(browser)")

    subgraph coffer_sys["Coffer"]
        web["React/TS SPA"]
        api["Coffer API<br/>FastAPI"]
    end

    pg[("PostgreSQL 16")]
    yahoo{{"Yahoo Finance<br/>(yfinance)"}}

    user -->|"HTTPS"| web
    web -->|"JSON /api/*, session cookie"| api
    api -->|"SQL (psycopg)"| pg
    api -->|"quotes, FX rates"| yahoo
```

The SPA talks only to the API under `/api/*`. The API stores data in Postgres, fetches market data from Yahoo Finance, and caches quotes in `market_quotes`, refreshed by the price job.

---

## 3. Local runtime

```mermaid
flowchart LR
    browser("Browser")
    vite["Vite dev server :5173<br/>proxy /api to localhost:8000"]
    api["make dev-api<br/>uvicorn coffer.main:app :8000"]
    pg[("Postgres 16 in Docker<br/>compose.yaml :5432")]
    yahoo{{"Yahoo Finance"}}
    prices["make prices<br/>(coffer.scripts.refresh_prices)"]

    browser --> vite --> api --> pg
    api -.-> yahoo
    prices -.-> yahoo
    prices -.-> pg
```

The Vite proxy keeps the API on the same origin as the SPA, so the `coffer_session` cookie (`HttpOnly`, `SameSite=Lax`) needs no CORS. `OriginMiddleware` rejects (403) POST/PUT/PATCH/DELETE requests whose `Origin` is not in `COFFER_ALLOWED_ORIGINS`. Migrations run with `make migrate`; quotes are refreshed with `make prices` or the optional in-process thread (`COFFER_PRICE_REFRESH_MINUTES`). Setup: [development.md](development.md).

---

## 4. Backend modules and dependencies

Each module is `coffer/<module>/{api.py, service.py, models.py, schemas.py}`: `api.py` is a thin router, `service.py` holds the logic and is the module's only public interface. `analytics` has only pure functions (no models, no DB).

```mermaid
flowchart LR
    main["coffer.main<br/>(create_app, routers)"]
    scripts["coffer.scripts<br/>(dump_openapi, seed_demo, refresh_prices)"]

    subgraph core_layer["Modules"]
        accounts["coffer.accounts<br/>(deps.CurrentUser)"]
        transactions["coffer.transactions"]
        budget["coffer.budget<br/>trend, net worth"]
        cash["coffer.cash<br/>opening balance"]
        imports["coffer.imports"]
        profile["coffer.profile"]
        portfolio["coffer.portfolio"]
        market["coffer.market<br/>service, scheduler"]
        analytics["coffer.analytics<br/>(pure: month, trend,<br/>net_worth, portfolio, allocation (target, gap), shares, ...)"]
        core["coffer.core<br/>config, db, money, months, origin"]
    end

    main --> accounts & transactions & budget & cash & imports & profile & portfolio & market
    main -->|"OriginMiddleware"| core
    main -->|"start_price_scheduler"| market
    scripts --> main
    scripts -->|"models"| accounts
    scripts -->|"models"| transactions
    scripts -->|"refresh_prices: quoted_symbols"| portfolio
    scripts -->|"fetch, store"| market

    accounts --> core
    transactions -->|"api: CurrentUser"| accounts
    transactions -->|"TxView"| analytics
    transactions --> core
    budget -->|"service.list_views"| transactions
    budget -->|"month_summary, trend"| analytics
    budget --> cash
    budget --> portfolio
    budget --> accounts
    budget --> core
    cash --> accounts
    cash --> core
    imports -->|"service (dedup_keys, category_hints, ...)"| transactions
    imports --> accounts
    imports --> core
    profile --> accounts
    profile --> core
    portfolio -->|"portfolio_summary"| analytics
    portfolio -.->|"valuation, loaded lazily"| market
    portfolio --> accounts
    portfolio --> core
    market -->|"money.quantize"| core
    market --> accounts
    analytics -->|"money, months"| core

    classDef pure fill:#e8f5e9,stroke:#2e7d32
    class analytics pure
```

An arrow means "imports / uses". `import-linter` enforces nine contracts: **"Analytics is pure"** (`coffer.analytics` may not import `sqlalchemy`, `fastapi` or `coffer.core.db`) and eight **"<module> does not read other modules' models"** contracts (a module may not import another module's `models`). Modules use each other only through `service.py` or public `analytics` dataclasses; all routers import `coffer.accounts.deps.CurrentUser` by convention. `portfolio` loads `market.service` lazily so it works without market data.

---

## 5. Frontend

Routes (`App.tsx`): `/` (Summary), `/transactions`, `/portfolio`, `/account`, `/login`, `/register`. Old `/import` redirects to `/transactions` and `/profile` to `/account`. CSV import and the add form are expandable panels in `TransactionsPage`; filters (month, type, category, source) and sorting (date, amount) run in the browser on one month's list. `AccountPage` combines the investment profile with security settings. Shared UI components live in `components/ui` (custom `Select`, `DatePicker`, `ConfirmDialog`, portal popover). All UI text is Polish (N06) in `i18n/pl.ts`; amounts arrive as strings and are only formatted, never summed.

**Look and shared pieces.** The theme is dark only; there is no theme switch. Colours, fonts and radii are semantic tokens in `index.css` (`@theme static`): `bg`, `surface`, `surface-2`, `border`, `text`, `muted`, `accent`, `positive`, `negative`, `warning`, `info` and the categorical `chart-1..7`. Feature code uses tokens only, so restyling means editing tokens or shared components. Geist and Geist Mono are self-hosted through `@fontsource-variable/*` (imported in `main.tsx`); no font CDN is used.

| Piece | Role |
|---|---|
| `lib/format.ts` | The only formatting module: `formatMoney`, `formatPct`, `signOf` (cached `Intl.NumberFormat('pl-PL')` per currency) |
| `components/Signed` | Amount or percentage coloured by sign (`positive` / `negative`), optional `+` and `invert` |
| `components/Money` | Plain amount, red only when negative |
| `components/ui/Stat` | Summary tile: label, value, optional delta |
| `components/ui/Bar`, `ui/BarList` | Progress/meter bar and a labelled list of bars (categories) |
| `features/portfolio/AllocationChart` | Hand-rolled SVG donut with legend (`role="img"` plus text legend); `compact` variant on Summary; colours from `chart-*`; optional `target` prop adds "cel" and gap rows (Summary and Portfolio) |

```mermaid
flowchart LR
    subgraph pages["src/frontend/src/features (React Router, App.tsx)"]
        auth["auth<br/>AuthPage, useMe"]
        tx["transactions<br/>TransactionsPage, TransactionRow, TransactionForm"]
        bud["budget<br/>SummaryPage, NetWorthCard, TrendChart, CategoryTrends"]
        imp["import<br/>ImportFlow (panel in TransactionsPage)"]
        prof["profile<br/>ProfileSection (in AccountPage)"]
        port["portfolio<br/>PortfolioPage"]
    end

    subgraph apilayer["API layer (TanStack Query in queries.ts)"]
        client["api/client.ts<br/>openapi-fetch, credentials: include"]
        schema["api/schema.d.ts<br/>(generated: make openapi)"]
        rawfetch["lib/apiFetch.ts<br/>(multipart)"]
        guard["401 outside /api/auth/*<br/>signOutLocally()"]
    end

    openapi["OpenAPI from FastAPI<br/>(coffer.scripts.dump_openapi)"]

    subgraph endpoints["Backend /api/*"]
        e_auth["/api/auth/{register,login,logout,me}"]
        e_tx["/api/transactions (GET, POST, PATCH, DELETE),<br/>/api/categories"]
        e_bud["/api/budget/{month}, /api/budget/{month}/trend?months=3, 6 or 12,<br/>/api/budget/net-worth"]
        e_imp["/api/imports, /api/imports/banks,<br/>/api/imports/{draft_id}/commit"]
        e_prof["/api/profile"]
        e_port["/api/portfolio/holdings, /api/portfolio/summary<br/>(holdings + positions with lots)"]
    end

    openapi -->|"openapi-typescript"| schema
    schema -.->|"paths types"| client
    auth & tx & bud & port --> client
    imp --> client
    imp --> rawfetch
    prof --> client
    prof --> rawfetch
    client --> guard
    rawfetch --> guard

    auth --> e_auth
    tx --> e_tx
    bud --> e_bud
    imp --> e_imp
    prof --> e_prof
    port --> e_port
```

Each feature has its own `queries.ts` (TanStack Query hooks) that call the typed `openapi-fetch` client. CSV upload and some profile calls go through `lib/apiFetch.ts`; both clients sign the user out locally on a 401 outside `/api/auth/*`.

---

## 6. Data model

```mermaid
erDiagram
    users ||--o{ auth_sessions : "has sessions"
    users ||--o{ transactions : "has"
    categories ||--o{ transactions : "categorizes"
    users ||--o{ import_drafts : "has drafts"
    users ||--o| investment_profiles : "has profile"
    users ||--o{ holdings : "has holdings"
    users ||--o| opening_balances : "opening balance"

    users {
        int id PK
        varchar email UK "254, unique lower(email)"
        varchar password_hash
        varchar display_name "50, required"
        timestamptz created_at
        timestamptz password_changed_at
        timestamptz last_login_at
    }
    auth_sessions {
        int id PK
        int user_id FK "ON DELETE CASCADE"
        varchar token_hash UK "SHA-256, 64"
        timestamptz expires_at
        timestamptz created_at
    }
    categories {
        int id PK
        varchar name UK
        bool in_budget
        bool is_default
    }
    transactions {
        int id PK
        int user_id FK "CASCADE, index (user_id, date)"
        date date
        numeric amount "NUMERIC(14,2), PLN"
        varchar description "500"
        int category_id FK
        varchar source "manual / import"
        bool needs_review
        timestamptz created_at
    }
    import_drafts {
        varchar id PK "UUID, 36"
        int user_id FK "CASCADE"
        varchar bank
        varchar filename
        jsonb rows
        timestamptz created_at
        timestamptz expires_at
    }
    investment_profiles {
        int user_id PK, FK "CASCADE, 1:1"
        varchar horizon "short / medium / long"
        varchar risk "low / medium / high"
        jsonb preferred_classes
        timestamptz updated_at
    }
    holdings {
        int id PK
        int user_id FK "CASCADE"
        varchar name
        varchar symbol "Yahoo ticker, optional"
        varchar asset_class
        numeric quantity "NUMERIC(20,8)"
        numeric purchase_price "NUMERIC(14,2)"
        varchar currency "default PLN"
        date purchase_date
        numeric manual_value "NUMERIC(14,2)"
        varchar note
        timestamptz created_at
    }
    opening_balances {
        int user_id PK, FK "CASCADE, 1:1"
        numeric amount "NUMERIC(14,2)"
        date as_of
        timestamptz updated_at
    }
    market_quotes {
        varchar symbol PK "20"
        date quote_date PK
        numeric price "NUMERIC(20,8)"
        varchar currency "3"
        numeric change_pct "NUMERIC(9,4)"
        varchar source "default yahoo"
        timestamptz fetched_at
    }
```

Money is `NUMERIC(14,2)` mapped to `Decimal`; `holdings.quantity` and `market_quotes.price` are `NUMERIC(20,8)` (units and instrument prices, not amounts). Every user-data table has `user_id` with `ON DELETE CASCADE`, so deleting an account is one `DELETE FROM users`. `categories` and `market_quotes` are global and hold no personal data. Migrations, known issues and the planned direction: [data-model.md](data-model.md).
