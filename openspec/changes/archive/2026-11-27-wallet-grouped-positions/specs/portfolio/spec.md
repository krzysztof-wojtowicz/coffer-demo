## ADDED Requirements

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
The Wallet page SHALL show one header row per position with its PLN totals, starting collapsed. Clicking the header SHALL expand or collapse its lots. Each lot SHALL have "Edytuj" and "Usuń" actions. The header row SHALL have none.

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
