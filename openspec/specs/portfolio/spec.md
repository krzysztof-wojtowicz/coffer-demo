# portfolio Specification

## Purpose
The user's investment portfolio: holdings, valuation in the base currency, allocation by asset class, gain/loss, and daily market-price refresh. Covers F20–F25 and N07 (former UC-04). Market data comes from Yahoo Finance (`yfinance`) through `coffer.market`; see `docs/mcp-market.md`.

## Requirements

### Requirement: Manage holdings (F20, F21)
A user SHALL be able to add, edit (`PATCH`, only sent fields change) and delete holdings at `/api/portfolio/holdings`. A holding has a name, an optional ticker symbol, an asset class (`stock`, `etf`, `bond`, `real_estate`, `commodity`, `crypto`, `cash`), a quantity, a purchase price, a currency (default PLN), an optional purchase date, an optional manual current value, and an optional note.

#### Scenario: Add a holding
- **WHEN** the user submits valid holding data
- **THEN** the holding is saved and the response is 201

#### Scenario: Invalid holding data
- **WHEN** the quantity is ≤ 0 or has more than 8 decimal places, a price is negative or has more than 2 decimal places, or the purchase date is in the future
- **THEN** the system responds 422 with Polish messages (e.g. "Data zakupu nie może być z przyszłości")

#### Scenario: Required field cleared on edit
- **WHEN** a PATCH sets name, asset class, quantity, purchase price or currency to null
- **THEN** the system responds 422

#### Scenario: Another user's holding
- **WHEN** the holding does not exist or belongs to another user
- **THEN** the system responds 404

### Requirement: Valuation and allocation (F22, F23, F24)
`GET /api/portfolio/summary` SHALL return each holding's current value in the base currency, the source of that value (`market`, `manual`, or `cost`), its gain or loss versus cost in PLN and percent, and its share of the portfolio. It SHALL also return the total value, the allocation per asset class, and `prices_as_of`.

#### Scenario: Market price available
- **WHEN** a holding has a symbol with a known quote
- **THEN** its value is quantity × price converted to PLN, with `value_source: market`

#### Scenario: No market price
- **WHEN** no quote is available and no manual value is set
- **THEN** the holding is valued at cost (`value_source: cost`) and the portfolio is flagged as incomplete

#### Scenario: Foreign currency
- **WHEN** the price is in another currency
- **THEN** it is converted to PLN at the daily FX rate and the holding is marked `converted`

### Requirement: Price refresh (F25)
Quotes and FX rates SHALL be cached in the global `market_quotes` table (one row per symbol and day). They SHALL be refreshed at least daily by `make prices` (`python -m coffer.scripts.refresh_prices`) or by an optional in-process thread (`COFFER_PRICE_REFRESH_HOURS`, default 0 = off, guarded by a Postgres advisory lock). Valuation SHALL read memory (5 min), then the database (today's quote), then the source.

#### Scenario: Several workers
- **WHEN** more than one API worker runs the refresh thread
- **THEN** only the one holding the advisory lock refreshes prices

### Requirement: Dated market data (N07)
Every piece of market information shown to the user SHALL carry the date it was fetched.

#### Scenario: Price date
- **WHEN** the portfolio is shown
- **THEN** the UI shows when prices were last updated (`prices_as_of`)

### Requirement: Works without AI (N08)
Portfolio features SHALL NOT depend on the AI agent.

#### Scenario: LLM unavailable
- **WHEN** no LLM provider is reachable
- **THEN** holdings, valuation and allocation work normally
