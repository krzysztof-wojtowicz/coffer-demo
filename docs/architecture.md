# Coffer architecture

How Coffer is built: key decisions, stack, modules, the AI agent, deployment and CI. The diagrams use [Mermaid](https://mermaid.js.org/) (GitHub renders them) and were drawn from the code: imports in `src/backend/coffer`, `coffer/main.py`, the `import-linter` contracts in `src/backend/pyproject.toml`, models and Alembic migrations, `src/frontend/src`, `render.yaml`, `vercel.json`, `compose.yaml` and `.github/`. Behaviour is specified in [`openspec/specs/`](../openspec/specs); the data model in detail is in [data-model.md](data-model.md).

**Guiding principle: the core computes, the agent interprets.** Every number the user sees (totals, shares, gains, purchase simulation) comes from `coffer.analytics`. The agent gets finished results through tools and writes the narrative. This makes exact totals (N04) and working without AI (N08) true by construction.

## Contents
1. [Decisions and stack](#1-decisions-and-stack)
2. [System context](#2-system-context)
3. [Deployment](#3-deployment)
4. [Backend modules and dependencies](#4-backend-modules-and-dependencies)
5. [Frontend](#5-frontend)
6. [Agent: running an action](#6-agent-running-an-action)
7. [MCP market-data server](#7-mcp-market-data-server)
8. [Data model](#8-data-model)
9. [CI/CD pipeline](#9-cicd-pipeline)

Legend: rectangle = Coffer component; rounded `( )` = person or external client; cylinder = database; hexagon `{{ }}` = external service; solid arrow = calls/uses; dashed arrow = optional, configuration or trigger; `subgraph` = boundary.

---

## 1. Decisions and stack

| Area | Decision |
|---|---|
| App type | Web, client–server, API-first. Accounts, sessions (N02) and keeping the LLM key off the client (N03) require a server. |
| Backend | Python 3.12, FastAPI with sync `def` endpoints, Pydantic v2, SQLAlchemy 2 (sync), Alembic, psycopg 3. Sync keeps the code simple; SSE uses a generator in `StreamingResponse`. |
| Frontend | React + TypeScript SPA (Vite), React Router, TanStack Query, Tailwind with semantic theme tokens. API types are generated from OpenAPI (`openapi-typescript` + `openapi-fetch`); CI checks they are current. |
| Database | PostgreSQL 16: `NUMERIC` for money, `ON DELETE CASCADE` for account deletion (N09), transactions for atomic import commits, `JSONB` for document-like data (import drafts, agent traces). |
| Auth | `argon2-cffi`, a session table, an HttpOnly + SameSite=Lax cookie. Deleting the session row revokes access immediately, which JWTs can't do. |
| AI agent | A module in the same backend behind `LLMClient`, with a rule-based fallback for every action. Own tool loop, no agent framework. Providers: Ollama (local default, `qwen3:8b`), OpenAI, Gemini, Anthropic, or `none`. |
| Market data | Yahoo Finance via `yfinance`, plus the Wikipedia REST API. No keys or paid services. |
| Hosting | Vercel (SPA) + Render (API, Docker) + Neon (Postgres). Vercel rewrites `/api/*` to Render, so the browser sees one origin. See [deploy/](deploy/README.md). |
| Quality | `uv`, `ruff`, `pyright`, `pytest`, `hypothesis`, `import-linter`; `tsc`, `vitest`. |
| Repository | Monorepo: `docs/`, `openspec/`, `src/backend/`, `src/frontend/`, `data/fixtures/`, `.claude/`. |

Rejected alternatives:
- **MongoDB.** The data is relational, and the hardest requirements are what a relational DB gives: exact decimals (N04), cascading deletes (N09), multi-row atomic import commits, and joins of per-user holdings with global quotes. `JSONB` covers the document-shaped parts.
- **Next.js.** No need for SEO or SSR, and it would add a second server next to Python.
- **Agent frameworks (LangChain etc.).** The tool loop is a few dozen lines; owning it keeps it transparent and testable.
- **Native provider tool-calling APIs.** Tools are called through a structured-output JSON protocol instead, so all providers and `FakeLLM` behave the same.

---

## 2. System context

```mermaid
flowchart LR
    user("User<br/>(browser)")
    mcpclient("MCP client<br/>Claude Desktop / Claude Code")

    subgraph coffer_sys["Coffer"]
        web["React/TS SPA"]
        api["Coffer API<br/>FastAPI"]
        mcpsrv["coffer.market.mcp_server<br/>(stdio process)"]
    end

    neon[("Neon Postgres")]
    yahoo{{"Yahoo Finance<br/>(yfinance)"}}
    llm{{"LLM provider<br/>Ollama / OpenAI / Gemini / Anthropic"}}

    user -->|"HTTPS"| web
    web -->|"JSON /api/*, session cookie"| api
    api -->|"SQL (psycopg)"| neon
    api -->|"quotes, news, FX rates"| yahoo
    api -.->|"aggregates only (optional)"| llm
    mcpclient -->|"MCP over stdio"| mcpsrv
    mcpsrv -->|"quotes, news"| yahoo
```

The SPA talks only to the API under `/api/*`. The API stores data in Postgres (Neon in production), fetches market data from Yahoo Finance, and optionally calls the LLM chosen by `COFFER_LLM_PROVIDER` (`ollama | openai | gemini | anthropic | none`). No LLM (`none`, an error, a limit) never breaks the core: every agent action has a rule-based result. Quotes are cached in `market_quotes` and refreshed by the price job. A separate `coffer.market.mcp_server` process exposes market tools to MCP clients and never touches the database or user data.

---

## 3. Deployment

```mermaid
flowchart TB
    browser("Browser")

    subgraph vercel["Vercel (root: src/frontend)"]
        spa["Static SPA (vite build, dist/)"]
        rewrite["Rewrite /api/:path* to Render<br/>other paths to /index.html"]
    end

    subgraph render["Render: Web Service coffer-api (Docker, free, Frankfurt)"]
        start["CMD: alembic upgrade head"]
        uvicorn["uvicorn coffer.main:app<br/>--proxy-headers"]
        origin["OriginMiddleware<br/>COFFER_ALLOWED_ORIGINS"]
        pricejob["price thread (optional)<br/>COFFER_PRICE_REFRESH_HOURS, default 0"]
        start --> uvicorn --> origin
        uvicorn -.-> pricejob
    end

    neonprod[("Neon Postgres<br/>direct URL, sslmode=require")]
    llmext{{"LLM API (COFFER_LLM_PROVIDER=gemini)"}}
    yahoo2{{"Yahoo Finance"}}

    subgraph github["GitHub"]
        ci["Actions: ci.yml"]
        deploy["Actions: deploy.yml"]
        dependabot["Dependabot"]
    end

    subgraph local["Local dev"]
        vite["Vite dev server :5173<br/>proxy /api to localhost:8000"]
        devapi["make dev-api (uvicorn :8000)"]
        pg[("Postgres 16 in Docker<br/>compose.yaml")]
        vite --> devapi --> pg
        prices["make prices<br/>(coffer.scripts.refresh_prices)"]
    end

    browser -->|"https://*.vercel.app"| spa
    browser -->|"/api/* + coffer_session cookie<br/>(same-origin via rewrite)"| rewrite
    rewrite -->|"https://coffer-api-p9ku.onrender.com/api/*"| uvicorn
    start -->|"migrations"| neonprod
    uvicorn -->|"SQL"| neonprod
    uvicorn -.-> llmext
    uvicorn -.-> yahoo2
    pricejob -.->|"UPSERT market_quotes"| neonprod
    pricejob -.-> yahoo2
    prices -.->|"CLI: quotes and FX rates"| yahoo2
    prices -.-> pg
    dependabot -.->|"PR"| ci
    ci -->|"workflow_run: success on main"| deploy
    deploy -->|"POST deploy hook ?ref=SHA"| render
    github -.->|"Git integration: push main = prod, PR = preview"| vercel
```

The browser sees only the Vercel domain: `vercel.json` rewrites `/api/:path*` to Render, so the `coffer_session` cookie (`HttpOnly`, `SameSite=Lax`, `Secure` via `COFFER_COOKIE_SECURE`) is first-party and needs no CORS. `OriginMiddleware` also rejects (403) POST/PUT/PATCH/DELETE requests whose `Origin` is not in `COFFER_ALLOWED_ORIGINS`. The Render container runs `alembic upgrade head` on start, then uvicorn; Neon is connected with the direct URL. Render has `autoDeploy: false`: `deploy.yml` deploys the backend through a deploy hook, while Vercel builds the frontend from Git. The price thread is off on Render free (`0`) because the instance sleeps; use `make prices` instead.

---

## 4. Backend modules and dependencies

Each module is `coffer/<module>/{api.py, service.py, models.py, schemas.py}`: `api.py` is a thin router, `service.py` holds the logic and is the module's only public interface. `analytics` has only pure functions (no models, no DB).

```mermaid
flowchart LR
    main["coffer.main<br/>(create_app, routers)"]
    scripts["coffer.scripts<br/>(dump_openapi, seed_demo, refresh_prices)"]

    subgraph agent_layer["Agent layer (coffer.agent)"]
        agent["coffer.agent<br/>api, service, runner, guard, trace, pricing,<br/>llm, validator, sse, schemas"]
        actions["coffer.agent.actions<br/>base (Action), catalog, 6 actions"]
        tools["coffer.agent.tools<br/>registry, user_data, market_data, calc<br/>(22 tools)"]
    end

    subgraph core_layer["Core (never imports coffer.agent)"]
        accounts["coffer.accounts<br/>(deps.CurrentUser)"]
        transactions["coffer.transactions"]
        budget["coffer.budget<br/>limits, insights"]
        cash["coffer.cash<br/>opening balance"]
        imports["coffer.imports"]
        profile["coffer.profile"]
        portfolio["coffer.portfolio"]
        market["coffer.market<br/>service, scheduler, tools, mcp_server"]
        analytics["coffer.analytics<br/>(pure: month, compare, limits, spending,<br/>planning, allocation, simulate, market_stats, ...)"]
        core["coffer.core<br/>config, db, money, months, origin"]
    end

    main --> accounts & transactions & budget & cash & imports & profile & portfolio & market & agent
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
    budget -->|"month_summary, compare, limit_status"| analytics
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

    agent -->|"run_action"| actions
    actions -->|"ctx.call"| tools
    tools -->|"service"| budget
    tools -->|"service"| profile
    tools -->|"service"| portfolio
    tools -->|"service"| market
    tools -->|"service"| transactions
    tools -->|"pure functions"| analytics
    actions -->|"pure functions"| analytics
    actions -->|"list_categories"| transactions
    agent --> accounts
    agent --> core

    classDef pure fill:#e8f5e9,stroke:#2e7d32
    classDef agentcls fill:#fff3e0,stroke:#ef6c00
    class analytics pure
    class agent,actions,tools agentcls
```

An arrow means "imports / uses". `import-linter` enforces two contracts: **"Core modules do not import the agent"** and **"Analytics is pure"** (`coffer.analytics` may not import `sqlalchemy`, `fastapi` or `coffer.core.db`). Modules use each other only through `service.py` or public `analytics` dataclasses; all routers import `coffer.accounts.deps.CurrentUser` by convention. Agent tools call only other modules' `service.py`. `portfolio` loads `market.service` lazily so it works without market data. `market.tools` serves only the MCP server.

---

## 5. Frontend

Routes (`App.tsx`): `/` (Summary), `/transactions`, `/portfolio`, `/assistant` (+ `/assistant/runs/:id`), `/account`, `/login`, `/register`. Old `/import` redirects to `/transactions` and `/profile` to `/account`. CSV import and the add form are expandable panels in `TransactionsPage`; filters (month, type, category, source) and sorting (date, amount) run in the browser on one month's list. `AccountPage` combines the investment profile with security settings. Shared UI components live in `components/ui` (custom `Select`, `DatePicker`, `ConfirmDialog`, portal popover). All UI text is Polish (N06) in `i18n/pl.ts`; amounts arrive as strings and are only formatted (`Intl.NumberFormat('pl-PL')`), never summed. The AI block is a separate component, so the rest of a page works when it fails (N08).

```mermaid
flowchart LR
    subgraph pages["src/frontend/src/features (React Router, App.tsx)"]
        auth["auth<br/>AuthPage, useMe"]
        tx["transactions<br/>TransactionsPage, TransactionRow, TransactionForm"]
        bud["budget<br/>SummaryPage, NetWorthCard, LimitsSection, InsightsCard"]
        imp["import<br/>ImportFlow (panel in TransactionsPage)"]
        prof["profile<br/>ProfileSection (in AccountPage)"]
        port["portfolio<br/>PortfolioPage"]
        asst["assistant<br/>AssistantPage (ActionPanel, SuggestionHistory, RunsTable), RunDetailPage"]
    end

    subgraph apilayer["API layer (TanStack Query in queries.ts)"]
        client["api/client.ts<br/>openapi-fetch, credentials: include"]
        schema["api/schema.d.ts<br/>(generated: make openapi)"]
        rawfetch["lib/apiFetch.ts<br/>(multipart, SSE)"]
        guard["401 outside /api/auth/*<br/>signOutLocally()"]
    end

    openapi["OpenAPI from FastAPI<br/>(coffer.scripts.dump_openapi)"]

    subgraph endpoints["Backend /api/*"]
        e_auth["/api/auth/{register,login,logout,me}"]
        e_tx["/api/transactions (GET, POST, PATCH, DELETE),<br/>/api/categories"]
        e_bud["/api/budget/{month}, /api/budget/{month}/insights,<br/>/api/budget/limits, /api/budget/net-worth"]
        e_imp["/api/imports, /api/imports/banks,<br/>/api/imports/{draft_id}/commit"]
        e_prof["/api/profile"]
        e_port["/api/portfolio/holdings, /api/portfolio/summary"]
        e_agent["/api/agent/{status,actions,tools},<br/>/api/agent/actions/{id}/run (JSON, SSE),<br/>/api/agent/suggestions, /api/agent/runs"]
    end

    openapi -->|"openapi-typescript"| schema
    schema -.->|"paths types"| client
    auth & tx & bud & port --> client
    imp --> client
    imp --> rawfetch
    prof --> client
    prof --> rawfetch
    asst --> client
    asst --> rawfetch
    client --> guard
    rawfetch --> guard

    auth --> e_auth
    tx --> e_tx
    bud --> e_bud
    imp --> e_imp
    prof --> e_prof
    port --> e_port
    asst --> e_agent
```

Each feature has its own `queries.ts` (TanStack Query hooks) that call the typed `openapi-fetch` client. CSV upload, the assistant's SSE stream and some profile calls go through `lib/apiFetch.ts`; both clients sign the user out locally on a 401 outside `/api/auth/*`. The *Plan budżetu* action can apply proposed limits (`ApplyLimits`). `/api/market/quotes` exists but the frontend does not use it yet.

---

## 6. Agent: running an action

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as AssistantPage (ActionPanel)
    participant API as agent.api
    participant G as agent.guard
    participant R as agent.runner
    participant A as Action (prepare, fallback, check)
    participant T as ToolRegistry (agent.tools)
    participant SV as module service.py + analytics
    participant LLM as LLMClient (agent.llm)
    participant DB as agent.service (agent_runs, suggestions, llm_usage_daily)

    U->>UI: pick action, params, "Run"
    UI->>API: POST /api/agent/actions/{id}/run {params}<br/>Accept: text/event-stream
    API->>API: CurrentUser, 404 unknown action, validate params (422)
    API->>R: run_action(db, user_id, action, params, llm, registry, on_event)
    R->>G: acquire(user_id)
    alt 20/min, 200/day or 2 concurrent exceeded
        G-->>API: ActionRateLimited
        API-->>UI: 429 (JSON) or error event (SSE)
    end
    R->>A: prepare(ctx, params)
    A->>T: ctx.call(tool, args)
    T->>SV: user data, quotes, calculations
    SV-->>T: result (amounts as strings)
    T-->>A: result (recorded as a trace step)
    A-->>R: Prepared {facts, tables, sources, context, snapshot, no_data?}
    alt no_data
        R->>R: status no_data, no model call
    else no LLM
        R->>R: status unavailable, rule-based result
    else daily limit used up (reserve_run)
        R->>R: status limited, rule-based result
    else model loop
        Note over R,LLM: The LLM gets only Prepared.context (aggregates) and results of the action's tools. No e-mail, transaction descriptions or ids.
        R->>R: db.commit + db.close (free the connection during the model call)
        loop up to action.max_steps, one COFFER_AGENT_TIMEOUT_S budget
            R->>LLM: complete(system, messages, response_schema)
            LLM-->>R: JSON {action: call_tool, tool, args | final, answer}
            opt call_tool
                R->>T: call(allowed tool, args)
                T-->>R: result (appended to conversation and trace)
            end
        end
        R->>R: validate_draft + action.check (numbers and sources only from tool results), up to 2 attempts
    end
    opt invalid, timeout, unavailable, limited
        R->>A: fallback(prepared, params)
        A-->>R: rule-based ReportDraft
    end
    R->>DB: add_run (trace: steps, tools, tokens, cost), record_usage
    opt source ai or rules
        R->>DB: add_suggestion (report, snapshots)
    end
    R->>G: release(user_id)
    R-->>API: ActionRunOut {ai_status, source, report, run_id, suggestion_id}
    API-->>UI: JSON or SSE: status, step, result
    UI-->>U: facts, tables, recommendations, sources, disclaimer, trace link
```

All six actions go through the same `runner` and differ only in their `Action` definition. `prepare` computes facts and tables from the core, the model adds narrative and recommendations, and the validator rejects numbers that are not in tool results. When the model is unavailable, too slow or wrong, the user still gets the rule-based result (`source: "rules"`). Every run is stored in `agent_runs` (including errors); `llm_usage_daily` counts only reservations with a model call.

### 6.1 Actions, tools, trace and limits

**Action interface** (`agent/actions/base.py`): an immutable `Action` with `id` (snake_case, stored in `agent_runs.task` and `suggestions.type`), name and description, `params_model` (Pydantic) and `params_ui` (form description), `prompt_version` (`agent/prompts/<version>.md`), `tools` (what the model may call), `draft_model` (the model's answer shape), `disclaimer`, the public flags `uses_user_data` / `uses_internet`, `prepare` (deterministic part), `fallback` (always possible) and optional `check`, and `max_steps`. `validate_catalog` checks catalog consistency (unknown tools, user-data tools in an action without user data, internet tools in an offline action).

| Action (`id`) | Parameters | Tools for the model |
|---|---|---|
| `portfolio_review` (Analiza portfela) | none | `get_portfolio`, `get_investment_profile`, `get_net_worth`, `target_allocation`, `get_price_history` |
| `investment_ideas` (Nowe możliwości inwestycyjne) | `month`, `amount`, `asset_class` (all optional) | `get_quotes`, `get_price_history`, `get_company_news`, `get_market_news`, `search_symbol`, `get_instrument_universe`, `simulate_purchase` |
| `savings_analysis` (Gdzie zaoszczędzić) | `month`, `months_back` (1–6) | `get_month_analysis`, `get_spending_insights`, `get_transaction_stats`, `get_category_limits`, `get_months_overview` |
| `purchase_impact` (Wpływ zakupu na portfel) | `asset_class`, `symbol`, `amount` or `quantity`, `price`, `currency` | `simulate_purchase`, `get_portfolio`, `get_investment_profile`, `target_allocation`, `get_quotes`, `get_fx_rate`, `get_month_analysis`, `get_price_history` |
| `budget_plan` (Plan budżetu) | `months_back` (1–6), `savings_target`, `target_months` | `get_months_overview`, `get_category_limits`, `propose_budget`, `savings_goal_plan`, `compound_interest` |
| `company_research` (Informacje o spółce) | `query` | `get_company_news`, `get_price_history`, `get_wikipedia_summary`, `get_quotes` (no user data) |

**Report schema.** Every action returns `ActionReport`: `headline`, `facts` (`{label, value, kind}`), `tables`, `findings`, `recommendations`, `risks`, `sources` (each with `fetched_at`) and `disclaimer`. Amounts and percents are strings. The model fills only the `ReportDraft` part (headline, 1–6 findings, 0–5 recommendations, 0–5 risks, 0–10 source URLs).

**Tool registry** (`agent/tools/registry.py`, `default_registry()`): 22 tools in three groups, each with an argument model, a Polish description and `uses_internet`. User data (8): `get_month_analysis`, `get_investment_profile`, `get_portfolio`, `get_net_worth`, `get_months_overview`, `get_spending_insights`, `get_transaction_stats`, `get_category_limits`. Calculations (5): `target_allocation`, `simulate_purchase`, `compound_interest`, `savings_goal_plan`, `propose_budget`. Market (9): `get_quotes`, `get_fx_rate`, `get_price_history`, `get_company_profile`, `get_company_news`, `get_market_news`, `search_symbol`, `get_wikipedia_summary`, `get_instrument_universe`. Tools get `user_id` from the session context, never from the model; a tool error does not stop the run (the model gets the message). User-data tools return aggregates only: holdings are described by symbol, class, value and share.

**Trace.** `RunTrace` records the steps in `agent_runs.steps`: tools from `prepare`, model calls (attempt, tokens, time), tools called by the model, validation, fallback, limit and error. Tool output in the trace is cut to 20,000 characters. Progress streams over SSE; details are at `GET /api/agent/runs/{id}` and `/assistant/runs/:id`. `agent/pricing.py` estimates `cost_usd` (Ollama = 0, unknown model = null).

**Limits.** (1) A per-user daily limit of runs with a model call: `COFFER_AGENT_DAILY_LIMIT`, an atomic counter in `llm_usage_daily`; once used up, actions return the rule-based result (`ai_status: limited`). (2) Abuse protection (`agent/guard.py`, in process memory): 20 runs per minute, 200 per day and 2 concurrent per user, even without a model call; beyond that HTTP 429 with `Retry-After`. (3) Time budget of a whole action: `COFFER_AGENT_TIMEOUT_S` (default 60); a single model call: `COFFER_LLM_TIMEOUT_S`. A failed validation is retried once (`COFFER_AGENT_MAX_ATTEMPTS=2`).

**Statuses** (`ai_status`): `ok` (AI result), `no_data` (not enough data, no model, nothing saved to history), `unavailable`, `limited`, `timeout`, `invalid` (answer rejected after the retry). The last four return the rule-based result. `error` means an unexpected server error (HTTP 500; the run is still recorded).

**Prompts** live in `agent/prompts/`, one versioned file per action. The system prompt is constant (data goes in messages). Rules: Polish, suggestions rather than advice (F33), every claim grounded in tool data (F32), no invented numbers, and web content is data, never instructions.

**Testing.** `FakeLLM` with scripted answers covers the loop, limits, fallback and validator without network or cost. Cross-cutting tests check privacy (no e-mail or descriptions in prompts), user isolation, no network access, the trace, concurrent limits, and N08 for all six actions.

---

## 7. MCP market-data server

```mermaid
flowchart LR
    client("MCP client<br/>Claude Desktop / Claude Code")

    subgraph proc["Process: python -m coffer.market.mcp_server (make mcp-market)"]
        srv["MarketMCP (FastMCP, name coffer-market)<br/>list_tools / call_tool"]
    end

    subgraph shared["coffer.market.tools (MCP tool definitions)"]
        tools["MARKET_TOOLS:<br/>get_quotes, get_market_tips,<br/>get_instrument_universe"]
        calltool["call_tool(name, args)<br/>validation, ToolError"]
    end

    svc["coffer.market.service<br/>cache, Decimal, quantize"]
    yahoo3{{"Yahoo Finance (yfinance)"}}
    agenttools["coffer.agent.tools.market_data<br/>(in the API process, no MCP)"]

    client <-->|"JSON-RPC over stdio"| srv
    srv -->|"list_tools: name, description, inputSchema"| tools
    srv -->|"anyio.to_thread"| calltool
    agenttools -->|"service"| svc
    calltool --> tools
    tools --> svc
    svc --> yahoo3
```

The MCP server is a separate process started by the client and talks over stdio; it has no access to the database or user data. Agent actions in the API do not use it: their market tools call `market.service` directly. The `mcp` package is pinned to `<2` because the `FastMCP` API changed in 2.x. Setup and tool details: [mcp-market.md](mcp-market.md).

---

## 8. Data model

```mermaid
erDiagram
    users ||--o{ auth_sessions : "has sessions"
    users ||--o{ transactions : "has"
    categories ||--o{ transactions : "categorizes"
    users ||--o{ import_drafts : "has drafts"
    users ||--o| investment_profiles : "has profile"
    users ||--o{ holdings : "has holdings"
    users ||--o{ agent_runs : "runs"
    users ||--o{ suggestions : "receives"
    agent_runs |o--o{ suggestions : "produced"
    users ||--o{ llm_usage_daily : "daily usage"
    users ||--o{ budget_limits : "sets limits"
    categories ||--o{ budget_limits : "category limit"
    users ||--o| opening_balances : "opening balance"

    users {
        int id PK
        varchar email UK "254, unique lower(email)"
        varchar password_hash
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
        numeric amount "NUMERIC(14,2)"
        varchar currency "default PLN"
        numeric base_amount "NUMERIC(14,2)"
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
    agent_runs {
        int id PK
        int user_id FK "CASCADE"
        varchar task "action id"
        varchar prompt_version
        varchar model
        varchar provider "ollama / openai / gemini / anthropic"
        varchar status "ok / no_data / unavailable / invalid / limited / timeout / error"
        jsonb params
        jsonb steps "trace"
        int llm_calls
        numeric cost_usd "NUMERIC(12,6)"
        jsonb tool_calls
        jsonb messages
        jsonb raw_outputs
        jsonb validation_errors
        int attempts
        int input_tokens
        int output_tokens
        int duration_ms
        timestamptz created_at
    }
    suggestions {
        int id PK
        int user_id FK "CASCADE"
        int agent_run_id FK "ON DELETE SET NULL"
        varchar type "action id"
        varchar month "YYYY-MM, optional"
        varchar source "ai / rules"
        varchar ai_status
        jsonb params
        varchar provider
        jsonb report "full action report"
        text summary
        jsonb rationale "optional"
        jsonb risks
        jsonb sources
        text disclaimer
        varchar model
        jsonb profile_snapshot
        jsonb data_snapshot
        timestamptz created_at
    }
    llm_usage_daily {
        int user_id PK, FK "CASCADE"
        date day PK
        int runs
        int input_tokens
        int output_tokens
    }
    budget_limits {
        int user_id PK, FK "CASCADE"
        int category_id PK, FK "RESTRICT"
        numeric amount "NUMERIC(14,2)"
        timestamptz created_at
        timestamptz updated_at
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

Money is `NUMERIC(14,2)` mapped to `Decimal`; `holdings.quantity` and `market_quotes.price` are `NUMERIC(20,8)` (units and instrument prices, not amounts). Every user-data table has `user_id` with `ON DELETE CASCADE`, so deleting an account is one `DELETE FROM users`. `categories` and `market_quotes` are global and hold no personal data. Suggestions survive deletion of their run (`SET NULL`). Migrations, known issues and the planned direction: [data-model.md](data-model.md).

---

## 9. CI/CD pipeline

```mermaid
flowchart TB
    push(["push to main"])
    pr(["pull request to main"])
    sched(["cron: Monday 05:00 UTC"])
    dep(["Dependabot: uv, npm, github-actions<br/>weekly, minor/patch groups"])

    subgraph ciwf["ci.yml (CI)"]
        be["backend<br/>Postgres 16 service, uv sync --locked,<br/>make lint (ruff, pyright, import-linter),<br/>pytest + coverage (artifact)"]
        fe["frontend<br/>npm ci, tsc --noEmit, vitest run, vite build"]
        oas["openapi-sync<br/>make openapi + git diff schema.d.ts"]
    end

    subgraph migwf["migrations.yml"]
        heads["exactly one Alembic head"]
        up["alembic upgrade head"]
        chk["alembic check (models = migrations)"]
        rt["downgrade base + upgrade head"]
        heads --> up --> chk --> rt
    end

    subgraph depwf["deploy.yml (workflow_run after CI)"]
        cond{"CI success<br/>and event = push?"}
        hook["curl POST RENDER_DEPLOY_HOOK_URL&ref=SHA"]
        skip["skipped"]
        cond -->|"yes"| hook
        cond -->|"no"| skip
    end

    renderbuild["Render: docker build (src/backend)<br/>alembic upgrade head, uvicorn"]
    vercelbuild["Vercel: build src/frontend<br/>main = production, PR = preview"]

    push --> ciwf
    pr --> ciwf
    pr -->|"changes in alembic/** or models.py"| migwf
    sched --> migwf
    dep -->|"opens PR"| pr
    ciwf -->|"completed"| cond
    hook --> renderbuild
    push -.->|"Git integration (outside Actions)"| vercelbuild
    pr -.->|"preview"| vercelbuild
```

`ci.yml` runs three parallel jobs (backend, frontend, openapi-sync) for pushes and PRs to `main`, with `COFFER_LLM_PROVIDER=none`. `deploy.yml` deploys only after a successful push-triggered CI run, and deploys exactly the tested commit (`ref=SHA`); without the `RENDER_DEPLOY_HOOK_URL` secret it is skipped. `migrations.yml` is the Alembic safety net. Dependabot ignores major versions of `mcp` and `typescript`. Details: [deploy/ci.md](deploy/ci.md).
