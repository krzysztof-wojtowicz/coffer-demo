# Architektura systemu Coffer

Dokument opisuje architekturę Coffer w formie diagramów [Mermaid](https://mermaid.js.org/), które GitHub renderuje natywnie. Wszystkie diagramy powstały na podstawie kodu i konfiguracji repozytorium: importów w `src/backend/coffer`, `coffer/main.py`, kontraktów `import-linter` w `src/backend/pyproject.toml`, modeli SQLAlchemy i migracji Alembic, `src/frontend/src`, `render.yaml`, `src/backend/Dockerfile`, `src/frontend/vercel.json`, `compose.yaml`, `.github/` oraz `docs/deploy/*.md` i `docs/mcp-market.md`.

## Spis treści

1. [Kontekst systemu (C4, poziom 1)](#1-kontekst-systemu-c4-poziom-1)
2. [Wdrożenie](#2-wdrożenie)
3. [Moduły backendu i zależności](#3-moduły-backendu-i-zależności)
4. [Frontend](#4-frontend)
5. [Sekwencja: „Pobierz rekomendacje” w Portfelu](#5-sekwencja-pobierz-rekomendacje-w-portfelu)
6. [Serwer MCP z danymi rynkowymi](#6-serwer-mcp-z-danymi-rynkowymi)
7. [Model danych](#7-model-danych)
8. [Pipeline CI/CD](#8-pipeline-cicd)

## Legenda

| Element | Znaczenie |
|---|---|
| Prostokąt | komponent Coffer (moduł, usługa, strona) |
| Prostokąt zaokrąglony `( )` | osoba lub klient zewnętrzny |
| Cylinder `[( )]` | baza danych |
| Romb / sześciokąt `{{ }}` | system zewnętrzny lub usługa chmurowa |
| `-->` strzałka ciągła | wywołanie / „używa” / przepływ danych |
| `-.->` strzałka przerywana | zależność opcjonalna, konfiguracyjna lub wyzwalacz |
| `subgraph` | granica (system, platforma hostingowa, warstwa) |

---

## 1. Kontekst systemu (C4, poziom 1)

```mermaid
flowchart LR
    user("Użytkownik<br/>(przeglądarka)")
    mcpclient("Klient MCP<br/>Claude Desktop / Claude Code")

    subgraph coffer_sys["Coffer"]
        web["SPA React/TS"]
        api["Coffer API<br/>FastAPI"]
        mcpsrv["coffer.market.mcp_server<br/>(proces stdio)"]
    end

    neon[("Neon Postgres")]
    yahoo{{"Yahoo Finance<br/>(yfinance)"}}
    llm{{"Dostawca LLM<br/>Ollama / OpenAI / Gemini / Anthropic"}}

    user -->|"HTTPS"| web
    web -->|"JSON /api/*, ciasteczko sesji"| api
    api -->|"SQL (psycopg)"| neon
    api -->|"notowania, newsy, kursy FX"| yahoo
    api -.->|"tylko agregaty (opcjonalne)"| llm
    mcpclient -->|"MCP przez stdio"| mcpsrv
    mcpsrv -->|"notowania, newsy"| yahoo
```

Użytkownik korzysta z Coffer przez przeglądarkę: SPA rozmawia wyłącznie z API pod `/api/*`. API przechowuje dane w Postgresie (produkcyjnie Neon), pobiera dane rynkowe z Yahoo Finance przez `yfinance` i opcjonalnie woła dostawcę LLM wybranego zmienną `COFFER_LLM_PROVIDER` (`ollama | openai | gemini | anthropic | none`). Brak LLM (`none` albo błąd) nie psuje rdzenia: doradca i asystent mają ścieżki zastępcze. Osobny proces `coffer.market.mcp_server` udostępnia te same narzędzia rynkowe klientom MCP (Claude Desktop/Code) i nie dotyka bazy ani danych użytkownika.

---

## 2. Wdrożenie

```mermaid
flowchart TB
    browser("Przeglądarka")

    subgraph vercel["Vercel (Root Directory: src/frontend)"]
        spa["Statyczne SPA (vite build, dist/)"]
        rewrite["Rewrite /api/:path* do Render<br/>pozostałe ścieżki do /index.html"]
    end

    subgraph render["Render: Web Service coffer-api (Docker, free, frankfurt)"]
        start["CMD: alembic upgrade head"]
        uvicorn["uvicorn coffer.main:app<br/>--proxy-headers"]
        origin["OriginMiddleware<br/>COFFER_ALLOWED_ORIGINS"]
        start --> uvicorn --> origin
    end

    neonprod[("Neon Postgres<br/>direct URL, sslmode=require")]
    llmext{{"LLM API (COFFER_LLM_PROVIDER=gemini)"}}
    yahoo2{{"Yahoo Finance"}}

    subgraph github["GitHub"]
        ci["Actions: ci.yml"]
        deploy["Actions: deploy.yml"]
        dependabot["Dependabot"]
    end

    subgraph local["Dev lokalnie"]
        vite["Vite dev server :5173<br/>proxy /api do localhost:8000"]
        devapi["make dev-api (uvicorn :8000)"]
        pg[("Postgres 16 w Dockerze<br/>compose.yaml")]
        vite --> devapi --> pg
    end

    browser -->|"https://*.vercel.app"| spa
    browser -->|"/api/* + ciasteczko coffer_session<br/>(same-origin dzięki rewrite)"| rewrite
    rewrite -->|"https://coffer-api-p9ku.onrender.com/api/*"| uvicorn
    start -->|"migracje"| neonprod
    uvicorn -->|"SQL"| neonprod
    uvicorn -.-> llmext
    uvicorn -.-> yahoo2
    dependabot -.->|"PR"| ci
    ci -->|"workflow_run: success na main"| deploy
    deploy -->|"POST deploy hook ?ref=SHA"| render
    github -.->|"Git integration: push main = prod, PR = preview"| vercel
```

Przeglądarka widzi tylko domenę Vercel: `vercel.json` przepisuje `/api/:path*` na `https://coffer-api-p9ku.onrender.com`, więc ciasteczko sesji `coffer_session` (`HttpOnly`, `SameSite=Lax`, `Secure` przez `COFFER_COOKIE_SECURE`) jest pierwszopartyjne i nie wymaga CORS. Dodatkowo `OriginMiddleware` odrzuca (403) żądania POST/PUT/PATCH/DELETE z nagłówkiem `Origin` spoza `COFFER_ALLOWED_ORIGINS`. Kontener Render (`src/backend/Dockerfile`) przy starcie wykonuje `alembic upgrade head`, potem uruchamia uvicorn; baza Neon jest podłączona direct URL-em (zalecenie z `docs/deploy/database.md`, pooled tylko z `-pooler` w hoście). Render ma `autoDeploy: false`: backend wdraża `deploy.yml` przez deploy hook, a frontend Vercel buduje sam z Git integration. Lokalnie Vite proxuje `/api` na `localhost:8000`, a Postgres działa w Dockerze z `compose.yaml`.

---

## 3. Moduły backendu i zależności

```mermaid
flowchart LR
    main["coffer.main<br/>(create_app, routery)"]
    scripts["coffer.scripts<br/>(dump_openapi, seed_demo)"]

    subgraph agent_layer["Warstwa agenta (coffer.agent)"]
        agent["coffer.agent<br/>api, service, llm, workflows.surplus,<br/>tools.registry, tools.user_data, validator"]
        invest["coffer.agent.investment<br/>api, advisor, schemas"]
    end

    subgraph core_layer["Rdzeń (nie importuje coffer.agent)"]
        accounts["coffer.accounts<br/>(deps.CurrentUser)"]
        transactions["coffer.transactions"]
        budget["coffer.budget"]
        imports["coffer.imports"]
        profile["coffer.profile"]
        portfolio["coffer.portfolio"]
        market["coffer.market<br/>service, tools, mcp_server"]
        analytics["coffer.analytics<br/>(czyste funkcje)"]
        core["coffer.core<br/>config, db, money, months, origin"]
    end

    main --> accounts & transactions & budget & imports & profile & portfolio & market & agent & invest
    main -->|"OriginMiddleware"| core
    scripts --> main
    scripts -->|"models"| accounts
    scripts -->|"models"| transactions

    accounts --> core
    transactions -->|"api: CurrentUser"| accounts
    transactions -->|"TxView"| analytics
    transactions --> core
    budget -->|"service.list_views"| transactions
    budget -->|"month_summary"| analytics
    budget --> accounts
    budget --> core
    imports -->|"service + models.Transaction (!)"| transactions
    imports --> accounts
    imports --> core
    profile --> accounts
    profile --> core
    portfolio -->|"portfolio_summary"| analytics
    portfolio --> accounts
    portfolio --> core
    market -->|"money.quantize"| core
    market --> accounts
    analytics -->|"money, months"| core

    agent -->|"service + schemas (!)"| budget
    agent -->|"service"| profile
    agent -->|"category_shares"| analytics
    agent --> accounts
    agent --> core
    invest -->|"llm.LLMClient"| agent
    invest -->|"service"| profile
    invest -->|"portfolio_summary"| analytics
    invest -->|"service + tools"| market
    invest --> accounts
    invest --> core

    classDef pure fill:#e8f5e9,stroke:#2e7d32
    classDef agentcls fill:#fff3e0,stroke:#ef6c00
    class analytics pure
    class agent,invest agentcls
```

Strzałka oznacza „importuje / używa” (na podstawie `grep "^from coffer"` w `src/backend/coffer`). Reguły z `CLAUDE.md` i `import-linter` (`src/backend/pyproject.toml`): kontrakt **„Core modules do not import the agent”** zabrania modułom z podgrupy „Rdzeń” importu `coffer.agent`, a **„Analytics is pure”** zabrania `coffer.analytics` importu `sqlalchemy`, `fastapi` i `coffer.core.db`; oba kontrakty są dziś spełnione (`lint-imports`: 2 kept, 0 broken). Moduły powinny używać siebie nawzajem przez `service.py` (lub publiczne dataclassy `analytics`); routery wszystkich modułów importują `coffer.accounts.deps.CurrentUser`, co jest przyjętą konwencją. Krawędzie oznaczone `(!)` wychodzą poza `service.py`: `imports.service` używa `transactions.models.Transaction`, a `agent.schemas` i `agent.workflows.surplus` używają `budget.schemas.MonthSummaryOut`; `agent.investment.advisor` korzysta z `market.tools`, czyli wspólnych definicji narzędzi (zamierzone, patrz diagram 6).

---

## 4. Frontend

Trasy (`App.tsx`): `/` (Podsumowanie), `/transactions`, `/portfolio`, `/assistant` (+ `/assistant/runs/:id`), `/account`, `/login`, `/register`. Stare `/import` przekierowuje do `/transactions`, `/profile` do `/account`. Import CSV i formularz dodawania to rozwijane panele w `TransactionsPage`; filtry (miesiąc, typ, kategoria, źródło) i sortowanie (data, kwota) działają po stronie klienta na liście jednego miesiąca. `AccountPage` łączy profil inwestycyjny (`ProfileSection`) z sekcją bezpieczeństwa. Wspólne komponenty UI w `components/ui` (m.in. własny `Select`, `DatePicker`, `ConfirmDialog`, popover w portalu).

```mermaid
flowchart LR
    subgraph pages["src/frontend/src/features (React Router, App.tsx)"]
        auth["auth<br/>AuthPage, useMe"]
        tx["transactions<br/>TransactionsPage, TransactionRow, TransactionForm"]
        bud["budget<br/>SummaryPage, NetWorthCard"]
        imp["import<br/>ImportFlow (panel w TransactionsPage)"]
        prof["profile<br/>ProfileSection (w AccountPage)"]
        port["portfolio<br/>PortfolioPage"]
        asst["assistant<br/>AssistantPage (AssistantPanel + AdvisorPanel), RunDetailPage"]
    end

    subgraph apilayer["Warstwa API (TanStack Query w queries.ts)"]
        client["api/client.ts<br/>openapi-fetch, credentials: include"]
        schema["api/schema.d.ts<br/>(generowany: make openapi)"]
        rawfetch["lib/apiFetch.ts<br/>(multipart, SSE)"]
        guard["401 poza /api/auth/*<br/>signOutLocally()"]
    end

    openapi["OpenAPI z FastAPI<br/>(coffer.scripts.dump_openapi)"]

    subgraph endpoints["Backend /api/*"]
        e_auth["/api/auth/{register,login,logout,me}"]
        e_tx["/api/transactions (GET, POST, PATCH, DELETE),<br/>/api/categories"]
        e_bud["/api/budget/{month}, /api/budget/net-worth"]
        e_imp["/api/imports, /api/imports/banks,<br/>/api/imports/{draft_id}/commit"]
        e_prof["/api/profile"]
        e_port["/api/portfolio/holdings, /api/portfolio/summary"]
        e_adv["/api/agent/investment/advice"]
        e_agent["/api/agent/status, /api/agent/surplus/stream,<br/>/api/agent/suggestions, /api/agent/runs"]
    end

    openapi -->|"openapi-typescript"| schema
    schema -.->|"typy paths"| client
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
    port --> e_adv
    asst --> e_agent
```

Każdy feature ma własne `queries.ts` (hooki TanStack Query), które wołają API przez typowany klient `openapi-fetch` z `api/client.ts`; typy `paths` pochodzą z `api/schema.d.ts`, generowanego z OpenAPI backendu przez `make openapi` (job `openapi-sync` w CI pilnuje, by był aktualny). Upload CSV, strumień SSE asystenta i część wywołań profilu idą przez `lib/apiFetch.ts`; oba klienty stosują tę samą politykę: 401 poza `/api/auth/*` wylogowuje lokalnie. Endpoint `/api/market/quotes` istnieje w backendzie, ale frontend go dziś nie używa.

---

## 5. Sekwencja: „Pobierz rekomendacje” w Portfelu

```mermaid
sequenceDiagram
    autonumber
    actor U as Użytkownik
    participant PP as AssistantPage / AdvisorPanel
    participant API as agent.investment.api
    participant PS as profile.service
    participant ADV as agent.investment.advisor
    participant AN as analytics.portfolio
    participant LLM as LLMClient (agent.llm)
    participant MT as market.tools
    participant MS as market.service
    participant Y as Yahoo Finance (yfinance)

    U->>PP: klik „Pobierz rekomendacje”
    PP->>API: POST /api/agent/investment/advice {holdings: symbol, asset_class, quantity, current_value}
    API->>API: CurrentUser (ciasteczko), get_llm_client()
    API->>PS: get(db, user.id)
    PS-->>API: InvestmentProfile albo None
    API->>ADV: advise(holdings, RiskProfile, llm)
    ADV->>AN: portfolio_summary(HoldingInput...)
    AN-->>ADV: udziały klas aktywów (%)
    opt llm nie jest None (COFFER_LLM_PROVIDER różny od none)
        loop maks. MAX_STEPS = 4
            ADV->>LLM: complete(system, messages, response_schema=RESPONSE_SCHEMA)
            Note over ADV,LLM: Do LLM trafia tylko: profil ryzyka, udziały klas %, symbole tickerów, wyniki narzędzi. Bez e-maila, nazw pozycji, kwot i identyfikatorów.
            LLM-->>ADV: JSON {action: call_tool | final}
            alt action = call_tool
                ADV->>MT: call_tool(name, args)
                MT->>MS: get_quotes / get_market_tips / get_instrument_universe
                MS->>Y: yf.Ticker(...).fast_info / get_news
                Y-->>MS: dane rynkowe
                MS-->>MT: Quote / MarketTip / Instrument
                MT-->>ADV: JSON (kwoty jako stringi)
            else action = final
                ADV->>ADV: _validate_answer (uniwersum, max_risk, znane URL-e)
            end
        end
    end
    alt brak LLM, wyjątek albo niepoprawna odpowiedź
        ADV->>MS: get_instrument_universe()
        ADV->>ADV: fallback_picks (scoring regułowy)
    end
    ADV->>MS: get_market_tips(3)
    MS->>Y: newsy
    ADV-->>API: AdviceOut {top_picks, tips, llm_used}
    API-->>PP: 200 JSON
    PP-->>U: 3 propozycje + wskazówki rynkowe
```

Frontend wysyła tylko zagregowane pozycje portfela (symbol, klasa, ilość, bieżąca wartość); profil ryzyka API czyta z `profile.service` (brak profilu oznacza domyślny `RiskProfile()`). Tool calling działa przez ustrukturyzowane wyjście: każdy krok `LLMClient.complete(response_schema=...)` zwraca albo `call_tool`, albo `final`, więc działa z każdym dostawcą (`OllamaClient`, `OpenAIClient`, `GeminiClient`, `AnthropicClient`). Odpowiedź modelu jest walidowana względem uniwersum instrumentów i maksymalnego ryzyka profilu; przy braku LLM, wyjątku lub złej odpowiedzi działa deterministyczny `fallback_picks`, a flaga `llm_used` mówi, która ścieżka zadziałała.

---

## 6. Serwer MCP z danymi rynkowymi

```mermaid
flowchart LR
    client("Klient MCP<br/>Claude Desktop / Claude Code")

    subgraph proc["Proces: python -m coffer.market.mcp_server (make mcp-market)"]
        srv["MarketMCP (FastMCP, nazwa coffer-market)<br/>list_tools / call_tool"]
    end

    subgraph shared["coffer.market.tools (wspólne definicje)"]
        tools["MARKET_TOOLS:<br/>get_quotes, get_market_tips,<br/>get_instrument_universe"]
        calltool["call_tool(name, args)<br/>walidacja, ToolError"]
    end

    svc["coffer.market.service<br/>cache, Decimal, quantize"]
    yahoo3{{"Yahoo Finance (yfinance)"}}
    advisor["coffer.agent.investment.advisor<br/>(w procesie API)"]

    client <-->|"JSON-RPC przez stdio"| srv
    srv -->|"list_tools: name, description, inputSchema"| tools
    srv -->|"anyio.to_thread"| calltool
    advisor -->|"opis narzędzi w prompcie"| tools
    advisor -->|"wywołania w pętli LLM"| calltool
    calltool --> tools
    tools --> svc
    svc --> yahoo3
```

Serwer MCP to osobny proces uruchamiany przez klienta (np. `claude mcp add coffer-market -- uv run --directory .../src/backend python -m coffer.market.mcp_server`) i komunikuje się przez stdio. Nazwy, opisy, schematy argumentów i walidacja narzędzi pochodzą z jednego miejsca, `coffer.market.tools`, więc klient MCP i doradca inwestycyjny widzą te same narzędzia i limity. Serwer nie ma dostępu do bazy ani do danych użytkownika: tylko publiczne dane rynkowe z `market.service`. Pakiet `mcp` jest przypięty do `<2` (Dependabot ignoruje major), bo w 2.x zmieniło się API `FastMCP`.

---

## 7. Model danych

```mermaid
erDiagram
    users ||--o{ auth_sessions : "ma sesje"
    users ||--o{ transactions : "ma"
    categories ||--o{ transactions : "kategoryzuje"
    users ||--o{ import_drafts : "ma szkice"
    users ||--o| investment_profiles : "ma profil"
    users ||--o{ holdings : "ma pozycje"
    users ||--o{ agent_runs : "uruchamia"
    users ||--o{ suggestions : "otrzymuje"
    agent_runs |o--o{ suggestions : "wygenerował"

    users {
        int id PK
        varchar email UK "254"
        varchar password_hash
        timestamptz created_at
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
        int user_id FK "CASCADE, indeks (user_id, date)"
        date date
        numeric amount "NUMERIC(14,2)"
        varchar currency "domyślnie PLN"
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
        varchar symbol "ticker Yahoo, opcjonalny"
        varchar asset_class
        numeric quantity "NUMERIC(20,8)"
        numeric purchase_price "NUMERIC(14,2)"
        varchar currency "domyślnie PLN"
        date purchase_date
        numeric manual_value "NUMERIC(14,2)"
        varchar note
        timestamptz created_at
    }
    agent_runs {
        int id PK
        int user_id FK "CASCADE"
        varchar task "np. surplus"
        varchar prompt_version
        varchar model
        varchar status "ok / no_surplus / unavailable / invalid / limited"
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
        varchar type "surplus"
        varchar month "YYYY-MM"
        text summary
        jsonb rationale
        jsonb risks
        jsonb sources
        text disclaimer
        varchar model
        jsonb profile_snapshot
        jsonb data_snapshot
        timestamptz created_at
    }
```

Tabele pochodzą z modeli `coffer/*/models.py` i migracji `alembic/versions/0001_initial` (users, auth_sessions, categories, transactions), `0002_import_drafts`, `0003_profile_agent` (investment_profiles, agent_runs, suggestions) i `0004_portfolio` (holdings). Kwoty pieniężne to `NUMERIC(14,2)` mapowane na `Decimal`; jedynie `holdings.quantity` ma `NUMERIC(20,8)`, bo to ilość jednostek, nie kwota. Każda tabela danych użytkownika ma `user_id` z `ON DELETE CASCADE`, a zapytania w `service.py` filtrują po nim; `categories` są globalne (słownik), a `suggestions` przeżywają usunięcie przebiegu agenta (`SET NULL`). Doradca inwestycyjny (diagram 5) nie zapisuje niczego do bazy.

---

## 8. Pipeline CI/CD

```mermaid
flowchart TB
    push(["push na main"])
    pr(["pull request do main"])
    sched(["cron: poniedziałek 05:00 UTC"])
    dep(["Dependabot: uv, npm, github-actions<br/>co tydzień, grupy minor/patch"])

    subgraph ciwf["ci.yml (CI)"]
        be["backend<br/>Postgres 16 service, uv sync --locked,<br/>make lint (ruff, pyright, import-linter),<br/>pytest + coverage (artefakt)"]
        fe["frontend<br/>npm ci, tsc --noEmit, vitest run, vite build"]
        oas["openapi-sync<br/>make openapi + git diff schema.d.ts"]
    end

    subgraph migwf["migrations.yml"]
        heads["dokładnie jedna głowa Alembic"]
        up["alembic upgrade head"]
        chk["alembic check (modele = migracje)"]
        rt["downgrade base + upgrade head"]
        heads --> up --> chk --> rt
    end

    subgraph depwf["deploy.yml (workflow_run po CI)"]
        cond{"CI success<br/>i event = push?"}
        hook["curl POST RENDER_DEPLOY_HOOK_URL&ref=SHA"]
        skip["pominięte (skipped)"]
        cond -->|"tak"| hook
        cond -->|"nie"| skip
    end

    renderbuild["Render: docker build (src/backend)<br/>alembic upgrade head, uvicorn"]
    vercelbuild["Vercel: build src/frontend<br/>main = produkcja, PR = preview"]

    push --> ciwf
    pr --> ciwf
    pr -->|"zmiany w alembic/** lub models.py"| migwf
    sched --> migwf
    dep -->|"otwiera PR"| pr
    ciwf -->|"completed"| cond
    hook --> renderbuild
    push -.->|"Git integration (poza Actions)"| vercelbuild
    pr -.->|"preview"| vercelbuild
```

`ci.yml` uruchamia trzy równoległe joby (backend, frontend, openapi-sync) dla pushy i PR-ów do `main`; w CI `COFFER_LLM_PROVIDER=none`, a testy podmieniają klienta LLM. `deploy.yml` startuje po każdym zakończonym CI na `main`, ale wdraża tylko po sukcesie wywołanym pushem, i to dokładnie przetestowany commit (`ref=SHA`); bez sekretu `RENDER_DEPLOY_HOOK_URL` krok jest pomijany. `migrations.yml` to siatka bezpieczeństwa dla Alembic (PR-y dotykające migracji lub modeli plus cotygodniowy cron). Dependabot otwiera PR-y, które przechodzą przez to samo CI; ignoruje major `mcp` i `typescript`, które psują build.
