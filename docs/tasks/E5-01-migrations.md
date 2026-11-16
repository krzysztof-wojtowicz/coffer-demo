# E5-01: Migracje 0007–0009 (ślad akcji, limity budżetu, notowania)

**Fala:** E5/0 · **Zależności:** E5-00 · **Role:** migracje (gimli) · **UC / wymagania:** F13, F14, F25, N07, N09; `data-model.md` §2.4, §2.6, §2.8

## Cel
Schemat bazy pod cały Etap 5 w jednym liniowym łańcuchu: rozszerzony ślad agenta i historia sugestii, atomowy limit dzienny, limity kategorii, trwałe notowania. Zmiany w `agent_runs`/`suggestions` są **addytywne**, więc obecny kod agenta działa dalej do czasu E5-03.

## Przeczytaj
- `docs/tasks/E5-00-architecture.md` (§K2, §K4, D5, D6, D8, D9)
- `src/backend/coffer/agent/models.py`, `src/backend/alembic/versions/0003_profile_agent.py`, `0006_opening_balance.py`, `src/backend/alembic/env.py`
- `docs/data-model.md` §2.6, §2.8 (`grep -n`)

## Pliki
- **gimli:** `src/backend/alembic/versions/{0007_agent_actions,0008_budget_limits,0009_market_quotes}.py`, `src/backend/alembic/env.py` (import nowych modeli), `src/backend/coffer/agent/models.py`, `src/backend/coffer/budget/models.py` (nowy), `src/backend/coffer/market/models.py` (nowy), `src/backend/tests/test_migrations_e5.py` (nowy)

## Kontrakt
**0007_agent_actions** (down: `0006`)
- `agent_runs`: nowe kolumny `provider varchar(20) NULL` (CHECK `IN ('ollama','openai','gemini','anthropic')`), `params jsonb NOT NULL DEFAULT '{}'`, `steps jsonb NOT NULL DEFAULT '[]'`, `llm_calls int NOT NULL DEFAULT 0` (CHECK `>= 0`), `cost_usd numeric(12,6) NULL` (CHECK `>= 0`); CHECK `status IN ('ok','invalid','unavailable','limited','timeout','no_data','error','no_surplus')`; indeksy `ix_agent_runs_user_id` i `ix_agent_runs_created_at` zastąpione `ix_agent_runs_user_id_created_at (user_id, created_at)`. `task` zostaje `varchar(30)` (id akcji ≤ 30).
- `suggestions`: `source varchar(10) NOT NULL DEFAULT 'ai'` (CHECK `IN ('ai','rules')`), `ai_status varchar(20) NOT NULL DEFAULT 'ok'`, `params jsonb NOT NULL DEFAULT '{}'`, `provider varchar(20) NULL`, `report jsonb` (backfill, potem `NOT NULL`), `rationale` → NULL-owalne; indeksy jak w `agent_runs` (`ix_suggestions_user_id_created_at`).
- Backfill `report` dla istniejących wierszy (jedno `UPDATE` w SQL): `headline = summary`, `facts = []`, `tables = []`, `findings` = `rationale[]` zmapowane na `{title: claim, detail: "", refers_to, value}`, `recommendations = []`, `risks`, `sources` = `sources[]` z `fetched_at = created_at` (brak `url` → pomiń element), `disclaimer`.
- Nowa tabela `llm_usage_daily (user_id FK users ON DELETE CASCADE, day date, runs int NOT NULL DEFAULT 0 CHECK >= 0, input_tokens int NOT NULL DEFAULT 0 CHECK >= 0, output_tokens int NOT NULL DEFAULT 0 CHECK >= 0, PK (user_id, day))`, indeks `ix_llm_usage_daily_day`.
- Downgrade: usuwa nowe kolumny/tabelę, przywraca indeksy, `rationale` NULL → `'[]'` i `NOT NULL`.

**0008_budget_limits** (down: `0007`): `budget_limits (user_id FK users CASCADE, category_id FK categories ON DELETE RESTRICT, amount numeric(14,2) NOT NULL CHECK > 0, created_at, updated_at, PK (user_id, category_id))`. Model `BudgetLimit` w `budget/models.py`.

**0009_market_quotes** (down: `0008`): `market_quotes (symbol varchar(20), quote_date date, price numeric(20,8) NOT NULL CHECK > 0, currency varchar(3) NOT NULL, change_pct numeric(9,4) NULL, source varchar(20) NOT NULL DEFAULT 'yahoo', fetched_at timestamptz NOT NULL, PK (symbol, quote_date))`. Tabela globalna, bez `user_id`. Model `MarketQuote` w `market/models.py`.

Modele ORM odpowiadają migracjom co do typów, nazw indeksów i ograniczeń (`alembic check` bez różnic). `AgentRun`/`Suggestion` zachowują wszystkie dotychczasowe atrybuty.

## Testy (gimli)
- `upgrade head` na czystej bazie, `downgrade 0006` i ponownie `upgrade head`.
- Backfill: wiersz `suggestions` typu `surplus` z 2 elementami `rationale` ma po migracji `report.findings` długości 2 i `report.headline == summary`.
- CHECK-i: zły `status`, `source`, `provider`, `amount <= 0`, `price <= 0`, ujemne `runs` → `IntegrityError`.
- Usunięcie użytkownika usuwa jego `llm_usage_daily` i `budget_limits`; usunięcie kategorii z limitem → `IntegrityError` (RESTRICT).

## Kryteria akceptacji
- [ ] `make lint`; `COFFER_TEST_DB=coffer_test_gimli make test-backend ARGS="tests/test_migrations_e5.py tests/agent"` (stare testy agenta nadal przechodzą)
- [ ] `alembic check` bez dryfu; jedna głowa `0009`
- [ ] workflow `migrations.yml` przejdzie (upgrade/downgrade)

## Poza zakresem
Logika `reserve_run` (E5-03), serwisy limitów (E5-02) i notowań (E5-04), `fx_rates` po dacie, `code` kategorii.
