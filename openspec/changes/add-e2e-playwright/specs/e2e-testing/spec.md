## ADDED Requirements

### Requirement: End-to-end coverage of key flows
The project SHALL have browser tests (`make e2e`) that cover registration, manual transactions (add, edit, delete), CSV import with duplicates, list filtering, portfolio and net worth, the AI advisor without a model, and logout redirects. Each scenario SHALL use its own user with a unique e-mail.

#### Scenario: Offline run
- **WHEN** `make e2e` runs
- **THEN** no request goes to yfinance or an LLM provider

#### Scenario: Suite budget
- **WHEN** the suite runs on a clean test database
- **THEN** it passes in under 3 minutes and leaves no data outside its own users
