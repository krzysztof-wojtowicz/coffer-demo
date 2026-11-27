# ai-agent Specification

## Purpose
The AI assistant ("Doradca AI"): an investment profile plus a catalog of six actions run by one engine, each producing a report with a rule-based fallback, a run trace, and suggestion history. Covers F30–F37, N03, N07 and N08 (former UC-05, UC-06, UC-07, UC-12, UC-13). Code lives in `coffer.agent`; the core never imports it.

## Requirements

### Requirement: Investment profile (F30)
A user SHALL be able to save an investment profile (`PUT /api/profile`) with an investment horizon (up to 2 years / 2–5 years / over 5 years), a risk tolerance (low / medium / high) and at least one preferred asset class, and read it back (`GET /api/profile`, null when not set). Changing the profile SHALL NOT change suggestions already produced.

#### Scenario: Incomplete profile
- **WHEN** the horizon or risk tolerance is missing or no asset class is selected
- **THEN** the system responds 422 and keeps the previous profile

### Requirement: Action engine
The system SHALL run any action through one endpoint, `POST /api/agent/actions/{id}/run` with `{params}`. It responds with JSON, or with SSE events (`status`, `step`, `result`, `error`, keepalive pings) when the request has `Accept: text/event-stream`. The model calls tools through a structured-output JSON protocol (`call_tool` / `final`) and may call only the tools allowed for the action.

#### Scenario: Streaming run
- **WHEN** the client sends `Accept: text/event-stream`
- **THEN** it receives step events as they happen and a final `result` event

### Requirement: Action catalog
The system SHALL list its actions (`GET /api/agent/actions`, with parameters for the UI form) and tools (`GET /api/agent/tools`). The catalog SHALL contain six actions: `portfolio_review` (Analiza portfela), `savings_analysis` (Gdzie zaoszczędzić), `purchase_impact` (Wpływ zakupu na portfel), `budget_plan` (Plan budżetu), `investment_ideas` (Nowe możliwości inwestycyjne) and `company_research` (Informacje o spółce).

#### Scenario: Unknown action
- **WHEN** the action id is not in the catalog
- **THEN** the system responds 404 "Nie znaleziono akcji"

#### Scenario: Invalid parameters
- **WHEN** the parameters fail the action's schema
- **THEN** the system responds 422 and does not call the model

### Requirement: Report with computed numbers (F32, F33)
Every action SHALL return one report schema: headline, facts, tables, findings, recommendations, risks, sources and a disclaimer. Facts and tables SHALL be computed deterministically by code (`coffer.analytics`); the model SHALL write only the narrative (headline, findings, recommendations, risks, source URLs). Every report SHALL include a disclaimer that it is not investment advice.

#### Scenario: Validation of the model's answer
- **WHEN** the model's answer contains a number, URL or symbol not present in tool results, or has no justification tied to the user's data
- **THEN** the answer is rejected and retried once (`COFFER_AGENT_MAX_ATTEMPTS`=2), then the rule-based result is returned with `ai_status: invalid`

### Requirement: Rule-based fallback (N08)
Every action SHALL have a rule-based result in the same report schema. When the LLM is unavailable, the daily limit is reached, the action times out (`COFFER_AGENT_TIMEOUT_S`, default 60 s) or the answer is invalid, the endpoint SHALL respond 200 with that result, `source: rules`, the matching `ai_status` (`unavailable`, `limited`, `timeout`, `invalid`), and a "bez AI" label in the UI. The rest of the app SHALL keep working without an LLM.

#### Scenario: LLM unavailable
- **WHEN** no provider responds
- **THEN** the user gets the rule-based report with `ai_status: unavailable`

#### Scenario: Not enough data
- **WHEN** the action cannot run on the user's data (e.g. no surplus and no amount given)
- **THEN** it ends with `ai_status: no_data` and a Polish message, without calling the model

### Requirement: Limits and abuse protection
AI runs SHALL count against a per-user daily limit (`COFFER_AGENT_DAILY_LIMIT`) reserved atomically before the model call (`llm_usage_daily`, `reserve_run`). Action runs SHALL also be rate limited (20 per minute, 200 per day, 2 concurrent).

#### Scenario: Rate limit exceeded
- **WHEN** a user exceeds the abuse-protection rate
- **THEN** the system responds 429 "Zbyt wiele uruchomień akcji…" with a `Retry-After` header

#### Scenario: Daily AI limit reached
- **WHEN** the daily AI limit is used up
- **THEN** the action still returns the rule-based report with `ai_status: limited`

### Requirement: Privacy of data sent to the LLM (N03)
Only aggregates SHALL be sent to the model: no e-mail, transaction descriptions, holding names or notes, or database identifiers. Holdings SHALL be described by symbol, asset class, value and share. `company_research` SHALL receive no user data at all.

#### Scenario: Prompt contents
- **WHEN** any action runs
- **THEN** the recorded messages contain no e-mail, transaction description or user/row id

### Requirement: Trace and history
Each run SHALL be stored in `agent_runs` with params, prompt version, steps (tool, llm, validation, fallback, limit and error steps with timings), provider, model, token usage and estimated cost. Each successful result (`ai` or `rules`) SHALL be stored as a suggestion; `no_data` and errors SHALL NOT be. Users SHALL be able to list and filter their runs (`GET /api/agent/runs`) and suggestions (`GET /api/agent/suggestions`), and open one by id; another user's id returns 404.

#### Scenario: Viewing a trace
- **WHEN** the user opens a past run
- **THEN** the UI shows the step timeline with tools called and their durations

### Requirement: Investment ideas (F31, F36)
`investment_ideas` SHALL take an optional month (default: previous month), amount and asset class. With no amount, it SHALL use the deterministic surplus of the month. It SHALL compute the allocation gap from the profile, pick candidates from a fixed instrument universe (risk level 1–5) that the user does not hold yet, and present the top 3 ideas with justification and dated market data. Without a profile, it SHALL use a default profile (medium risk, medium horizon) and say so.

#### Scenario: No surplus and no amount
- **WHEN** the month's surplus is 0 and no amount is given
- **THEN** the action ends with `no_data` "Brak nadwyżki w wybranym miesiącu. Podaj kwotę ręcznie."

#### Scenario: No candidates
- **WHEN** no instrument matches the criteria
- **THEN** the action ends with `no_data` "Brak instrumentów spełniających kryteria. Zmień klasę aktywów."

### Requirement: Purchase impact (F37)
`purchase_impact` SHALL take an asset class, an optional symbol, an amount or a quantity with an optional price, and a currency. It SHALL show asset-class shares before and after the purchase (`analytics.simulate_purchase`) and report the previous month's surplus as a fact ("Kwota w granicach nadwyżki: tak/nie"), not as a blocker. The portfolio SHALL NOT change.

#### Scenario: Unknown price
- **WHEN** the asset's price cannot be found and no price or PLN amount is given
- **THEN** the action ends with `no_data` asking for a price

#### Scenario: Empty portfolio
- **WHEN** the portfolio is empty
- **THEN** the asset is shown as 100% of the portfolio after the purchase

### Requirement: Company research (F34, F35, N07)
`company_research` SHALL take a company name or ticker (1–60 characters), gather quotes, profile, news and a Wikipedia summary, and return a summary with a list of source URLs, each with a fetch date. A summary with no source SHALL NOT be shown.

#### Scenario: Nothing found
- **WHEN** the search returns no results
- **THEN** the system says no information was found and suggests checking the name or ticker

### Requirement: Budget actions (F12, F13, F15, F17, F31)
`savings_analysis` SHALL analyze spending changes and limit overruns over 1–6 months. `budget_plan` SHALL propose category limits and, given a savings target and a number of months (1–120), the monthly amount to save; the user SHALL be able to apply proposed limits with one click.

#### Scenario: Apply proposed limits
- **WHEN** the user applies the limits from a budget plan
- **THEN** they are saved through the budget limits API

### Requirement: Portfolio review
`portfolio_review` SHALL assess the whole portfolio's allocation against the investment profile, with computed shares as facts.

#### Scenario: Review
- **WHEN** the user runs the action with a non-empty portfolio
- **THEN** the report shows allocation facts and findings tied to the profile
