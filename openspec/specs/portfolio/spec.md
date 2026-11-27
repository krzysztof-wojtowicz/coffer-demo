# portfolio Specification

## Purpose
The user's investment portfolio: holdings, valuation in the base currency, allocation by asset class, gain/loss, and daily market-price refresh. Covers F20–F25, F30 (investment profile) and N07 (former UC-04). Market data comes from Yahoo Finance (`yfinance`) through `coffer.market`.

## Requirements

### Requirement: Manage holdings (F20, F21)
A user SHALL be able to add, edit (`PATCH`, only sent fields change) and delete holdings at `/api/portfolio/holdings`. A holding has a name, an optional ticker symbol, an asset class from the shared list (`stock`, `etf`, `bond`, `real_estate`, `commodity`, `crypto`, `cash`), a quantity, a purchase price, a currency (default PLN), an optional purchase date, an optional manual current value, and an optional note.

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
Quotes and FX rates SHALL be cached in the global `market_quotes` table (one row per symbol and day). They SHALL be refreshed by `make prices` (`python -m coffer.scripts.refresh_prices`) or by an in-process thread that runs every `COFFER_PRICE_REFRESH_MINUTES` minutes (default 0 = off, at most 1440, guarded by a Postgres advisory lock). Valuation SHALL read memory (5 min), then the database (today's quote), then the source.

#### Scenario: Several workers
- **WHEN** more than one API worker runs the refresh thread
- **THEN** only the one holding the advisory lock refreshes prices

#### Scenario: Periodic refresh
- **WHEN** `COFFER_PRICE_REFRESH_MINUTES` is 5 and the API runs
- **THEN** quotes for every held symbol and the FX rates they need are fetched again about every 5 minutes, and today's row in `market_quotes` is updated

#### Scenario: Refresh disabled
- **WHEN** `COFFER_PRICE_REFRESH_MINUTES` is 0
- **THEN** no refresh thread starts and quotes change only through `make prices` or on-demand valuation

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

### Requirement: Investment profile (F30)
A user SHALL be able to save an investment profile (`PUT /api/profile`) with an investment horizon (up to 2 years / 2–5 years / over 5 years), a risk tolerance (low / medium / high) and at least one preferred asset class from the shared list used by holdings, and read it back (`GET /api/profile`, null when not set).

#### Scenario: Save and read back
- **WHEN** the user saves a complete profile
- **THEN** `GET /api/profile` returns the saved horizon, risk tolerance and asset classes

#### Scenario: Incomplete profile
- **WHEN** the horizon or risk tolerance is missing or no asset class is selected
- **THEN** the system responds 422 and keeps the previous profile

#### Scenario: Unknown asset class
- **WHEN** the preferred classes contain a code outside the shared list (e.g. the old `stocks` or `deposit`)
- **THEN** the system responds 422 and keeps the previous profile

### Requirement: Target allocation
`GET /api/profile` SHALL return a `target` list of `{asset_class, share_pct}` computed only from the horizon, risk tolerance and preferred classes. Shares SHALL be whole percents summing to 100 and include only preferred classes with a share above 0. The base split comes from a fixed risk × horizon table, and each unselected class's share SHALL move to its nearest selected class.

#### Scenario: Base allocation
- **WHEN** a profile has medium risk, a 2–5 year horizon and all seven classes selected
- **THEN** the target is stock 11, etf 34, bond 40, cash 10, commodity 5

#### Scenario: Unselected class is redistributed
- **WHEN** the same profile selects every class except `stock`
- **THEN** the target is etf 45, bond 40, cash 10, commodity 5

#### Scenario: Longer horizon raises equity
- **WHEN** two profiles have the same risk and selected classes, which include bond or cash, but different horizons
- **THEN** the longer horizon has a stock + etf share at least as high as the shorter one

#### Scenario: Profile card
- **WHEN** the user opens the Account page with a saved profile
- **THEN** the profile card shows the horizon, the risk and the target allocation as a pie chart with a legend

### Requirement: Gap from target allocation
When a profile exists, `GET /api/portfolio/summary` SHALL return for each class in the target or the portfolio its current share, target share (0 if not in the target) and gap (current minus target, in percentage points). It SHALL also return the total gap: half the sum of absolute gaps. With no profile these fields SHALL be null; with no valued holdings the gaps SHALL be null.

#### Scenario: Gap per class
- **WHEN** the portfolio is 52% etf, 20% bond and 28% cash and the target is etf 34, bond 40, cash 10, stock 11, commodity 5
- **THEN** the gaps are etf +18, bond −20, cash +18, stock −11, commodity −5, and the total gap is 36

#### Scenario: No profile
- **WHEN** the user has no investment profile
- **THEN** the target fields are null and the pie chart shows only current shares, with a link to set up the profile

#### Scenario: Empty portfolio
- **WHEN** the user has a profile but no valued holdings
- **THEN** the target shares are returned, the per-class gaps and the total gap are null, and the UI shows the target without a comparison

#### Scenario: Pie chart shows the gap
- **WHEN** the Summary or Wallet page shows the allocation pie chart and a profile exists
- **THEN** each legend row shows the current share, the target share and the signed gap in pp, and the total gap is shown below the legend
