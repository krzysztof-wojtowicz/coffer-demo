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

### Requirement: Grouped positions (F22, F23)
`GET /api/portfolio/summary` SHALL return a `positions` list next to `holdings`. Holdings whose tickers match after trimming and upper-casing SHALL form one position, whatever their currency or asset class. Each holding without a ticker SHALL be its own position. A position SHALL take the name and asset class of its newest holding (latest purchase date, then latest creation).

#### Scenario: Same ticker grouped
- **WHEN** the user holds three AAPL holdings and one VWCE.DE holding
- **THEN** `positions` has two entries: AAPL with three lots and VWCE.DE with one lot

#### Scenario: Ticker case and spaces ignored
- **WHEN** one holding has the ticker `aapl` and another ` AAPL `
- **THEN** both belong to the same position, shown with the ticker `AAPL`

#### Scenario: Holding without a ticker
- **WHEN** the user has two real-estate holdings without a ticker
- **THEN** each is its own position with one lot

#### Scenario: Different currencies grouped
- **WHEN** one AAPL holding was bought in USD and another in PLN
- **THEN** both are lots of one AAPL position

#### Scenario: Newest name
- **WHEN** an older AAPL lot is named "Apple" and the newest is named "Apple Inc."
- **THEN** the position is named "Apple Inc."

### Requirement: Position totals in PLN
Each position SHALL carry, in PLN: total quantity, cost, current value, gain (amount and percent), share of the portfolio value and average purchase price per unit (cost ÷ quantity). Money SHALL be rounded half-up to 2 places and percents to 0.1. If any lot of the position has no FX rate to PLN, all of these totals SHALL be null.

#### Scenario: Totals of a position
- **WHEN** an AAPL position has lots valued at 4 000 PLN (cost 3 000 PLN, 5 units) and 2 000 PLN (cost 2 000 PLN, 5 units), in a portfolio worth 10 000 PLN
- **THEN** the position shows quantity 10, cost 5 000 PLN, value 6 000 PLN, gain 1 000 PLN (+20.0%), share 60.0% and average price 500.00 PLN

#### Scenario: Lot without an FX rate
- **WHEN** one lot of a position is in a currency without an FX rate
- **THEN** the position's PLN totals are null, the UI shows "–" for them, and each lot still shows its own-currency amounts

### Requirement: Lot amounts in their own currency
Each lot of a position SHALL identify its holding and show, in the holding's own currency: purchase date, quantity, purchase price per unit, cost, current value, value source and gain (amount and percent). A market price quoted in another currency SHALL be converted through the daily PLN rates. Lots SHALL be ordered by purchase date, oldest first; lots without a date come last.

#### Scenario: Foreign-currency lot
- **WHEN** a lot of 5 AAPL was bought at 150.00 USD and AAPL is quoted at 200.00 USD
- **THEN** the lot shows cost 750.00 USD, value 1 000.00 USD and gain +250.00 USD (+33.3%)

#### Scenario: Quote in a different currency than the lot
- **WHEN** a lot was bought in PLN and its ticker is quoted in USD, with both rates known
- **THEN** the lot's value is the quote converted to PLN, shown in PLN

#### Scenario: Lot order
- **WHEN** a position has lots bought on 2024-09-02, 2024-03-01 and with no date
- **THEN** they are listed 2024-03-01, 2024-09-02, then the undated lot

### Requirement: Wallet positions list
The Wallet page SHALL show one header row per position with its quantity and its PLN cost, value, gain and share (the average purchase price stays in the API only), starting collapsed. Clicking the header SHALL expand or collapse its lots. Each lot SHALL have "Edytuj" and "Usuń" actions. The header row SHALL have none.

#### Scenario: Expand a position
- **WHEN** the user clicks the AAPL header
- **THEN** its lots appear below it, each with "Edytuj" and "Usuń", and a second click hides them

#### Scenario: Single-lot position
- **WHEN** a position has one lot
- **THEN** it still shows a collapsed header row, and expanding it shows that lot

#### Scenario: Edit a lot
- **WHEN** the user clicks "Edytuj" on a lot
- **THEN** the holding form opens above the list, filled in with that holding

### Requirement: Wallet filters and sorting
Above the positions list the Wallet page SHALL offer an asset-class filter, a search on name or ticker, a sort key (value, name, gain in PLN, gain %, purchase date of the newest lot) and a direction. Filtering and sorting SHALL apply to positions, not lots. They SHALL NOT change the summary tiles or the allocation chart. The default is value, descending.

#### Scenario: Filter by asset class
- **WHEN** the user picks "ETF"
- **THEN** only ETF positions are listed and the total value tile is unchanged

#### Scenario: Search
- **WHEN** the user types "vwce"
- **THEN** only positions whose name or ticker contains "vwce" (case-insensitive) are listed

#### Scenario: Sort by gain
- **WHEN** the user sorts by gain %, descending
- **THEN** positions are ordered from the highest gain % to the lowest, with positions whose gain % is null last

#### Scenario: Nothing matches
- **WHEN** the filters match no position
- **THEN** the list shows "Brak pozycji spełniających filtry."

### Requirement: Add position above the list
The "Dodaj pozycję" button SHALL sit above the positions list and toggle the holding form in a card at the same place, as on the Transactions page.

#### Scenario: Open and close the form
- **WHEN** the user clicks "Dodaj pozycję" and then clicks it again
- **THEN** the empty form opens above the list and then closes

#### Scenario: Empty wallet
- **WHEN** the user has no holdings
- **THEN** the list says "Nie masz jeszcze żadnych pozycji. Dodaj pierwszą inwestycję przyciskiem powyżej."
