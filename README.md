# Coffer

Coffer is a personal-finance app. It gathers your transactions and investments in one place, works out how much you have left each month, and uses an AI assistant to analyse your budget and portfolio and suggest what to do with your money. The app's interface is in Polish.

> Coffer currently runs **locally only** (no hosted version) while the project is being refactored. See [Running locally](#running-locally).

<!-- TODO: screenshots -->

## What Coffer does

**Transactions and bank import**
- Add transactions by hand (date, amount, description, category) or import a bank-statement CSV. Both forms open as panels at the top of the *Transakcje* tab.
- The list has filters (month, type, category, source) and sorting (date or amount). Each row shows the date, amount, description, a coloured category tag and the source.
- *Edytuj* changes the date, amount, description and category inline (one transaction at a time); deleting asks for confirmation.
- Before importing you see a preview: which rows are new, which duplicate saved transactions, and which have errors. You decide what to import.
- Imported transactions are categorized automatically; ones that couldn't be matched are flagged "do sprawdzenia" (to review).

**Summary**
- The *Majątek* (net worth) card shows cash on accounts, portfolio value and net worth. Cash is the opening balance you enter (amount and date) plus your transactions since that date. Without one, all transactions count from zero, so the result may not match your bank. The card flags a portfolio that isn't fully priced.
- For the chosen month: income, expenses and balance tiles (all transactions). The surplus (budget categories only) is the default amount for *Nowe możliwości inwestycyjne*.
- Expenses by category with shares, a comparison with the previous month, and an *Wnioski* (insights) card with the fastest-growing categories.
- Monthly category limits, with usage shown in the list.
- A short portfolio card.

**AI Advisor** (*Doradca AI* tab) is a catalog of six actions. Pick one, fill in its parameters and run it. The result combines facts and tables computed by the app with a description and recommendations from the model.
- *Analiza portfela*: assesses your portfolio's structure against your profile.
- *Nowe możliwości inwestycyjne*: instrument ideas (amount defaults to the month's surplus; optional asset class).
- *Gdzie zaoszczędzić*: expenses you could cut, based on recent months.
- *Wpływ zakupu na portfel*: how a planned purchase changes allocation and concentration.
- *Plan budżetu*: proposed category limits, optionally for a savings goal; apply them with one click.
- *Informacje o spółce*: quotes, news and a company description by name or ticker.
- Before running, you see exactly what data will be sent to the model. Progress streams live, and every run has a **trace**: steps, tools called, time and usage.
- If the model is missing, unavailable or your limit is used up, you get a **rule-based result**: the computed facts and simple conclusions, labelled "bez AI". If there isn't enough data, the action says so and doesn't call the model.
- Suggestion and run history covers all actions.

**Investment profile** (top of the *Konto* tab)
- Three questions: investment horizon, risk tolerance and preferred asset classes.
- Coffer shows your profile (cautious, moderate, dynamic) with an indicative allocation, and the assistant's actions tailor their ideas to it.

**Portfolio**
- Holdings: stocks, ETFs, bonds, commodities, crypto, real estate, cash and deposits, in any currency.
- Holdings with a ticker (e.g. `AAPL`, `CDR.WA`, `BTC-USD`) are valued at current quotes, and foreign amounts are converted to PLN at the current rate. Assets without quotes (e.g. a flat) are valued by hand.
- Portfolio value, cost, gain or loss, and allocation by asset class.

**Account**
- Register with e-mail and password, log in and out. Everyone sees only their own data.
- The *Konto* page: the investment profile on top, then *Bezpieczeństwo konta* (change password, log out of all devices, permanently delete the account with all data).
- Five tabs (*Podsumowanie*, *Transakcje*, *Portfel*, *Doradca AI*, *Konto*); the header has a light/dark theme switch, your e-mail and *Wyloguj*.

## Running locally
```bash
cp .env.example .env   # optional
make setup && make db-up && make migrate && make seed
make dev-api            # terminal 1, http://localhost:8000
make dev-web            # terminal 2, http://localhost:5173
```
Demo account: `demo@coffer.local` / `coffer-demo-2026`. Requirements, AI model setup and troubleshooting: [docs/development.md](docs/development.md).

## Getting started
1. **Create an account** in your local app (<http://localhost:5173>): an e-mail and a password (at least 12 characters, not a common password or your e-mail).
2. **Add transactions** in *Transakcje*, by hand or by CSV import ([supported format](docs/csv-format.md)).
3. **Check the monthly summary** on the home page.
4. **Fill in your investment profile** in *Konto*; without it, suggestions are less tailored.
5. **Add your portfolio** in *Portfel*: holdings, quantities, purchase prices.
6. **Run an action** in *Doradca AI*, e.g. a portfolio review, a budget plan or investment ideas.

## Privacy and security
- **Only aggregates reach the AI model:** monthly totals and spending per category, asset-class shares, instrument symbols and your investment profile. Never your e-mail, transaction descriptions or identifiers.
- **The app computes, the model describes.** All totals and valuations come from Coffer's code. If the model is unavailable, the rest of the app works normally.
- **Local or cloud model.** By default the model runs locally in Ollama, so nothing leaves your machine. With a cloud provider (Gemini, OpenAI, Claude) the aggregates are processed under that provider's terms.
- **Passwords** are stored only as Argon2 hashes.
- **The session** lives in an `HttpOnly` cookie that page scripts can't read, and state-changing requests from other domains are rejected.

## Disclaimer
The assistant's results are informational and educational. **They are not investment advice.** Investing carries the risk of losing capital, and you make your own decisions. Quotes and exchange rates come from Yahoo Finance and may be delayed or temporarily unavailable.

## Limitations
- **Assistant limits:**
  - a daily limit of model runs per user (`COFFER_AGENT_DAILY_LIMIT`, 50 by default); when it runs out you get rule-based results.
  - abuse protection of 20 action runs per minute, 200 per day and 2 concurrent; beyond that the API returns 429.
- **CSV import** supports one file format for now ([docs/csv-format.md](docs/csv-format.md)), not specific banks' statements.
- **Quotes and FX rates** come only from Yahoo Finance. When they're unavailable, holdings use the manual value or purchase price, and holdings that can't be converted to PLN are left out of the total.
- The *Majątek* card counts cash from the opening balance you enter. Without one it counts from zero. Multiple bank accounts and transfers between them aren't supported.
- Transaction filters and sorting run in the browser, on one month's transactions.

## FAQ
**Does Coffer connect to my bank?**
No. You add transactions by hand or import a CSV file. Coffer never asks for your bank login.

**Does the AI model see my transactions?**
No. It sees only aggregates: monthly totals, spending per category, your portfolio's percentage structure and instrument symbols. The assistant page shows exactly what will be sent.

**Will importing the same file twice duplicate transactions?**
No. The import preview marks transactions already in Coffer (same date, amount and description) as duplicates and skips them by default.

**Why does the assistant say it's unavailable?**
The model isn't responding right now, or you've used your daily limit. The action then shows a rule-based result, and the summary, transactions and portfolio keep working. Try again later.

**Why does a holding show "cena zakupu" (purchase price) instead of "notowanie" (quote)?**
The current quote couldn't be fetched: no symbol, an unknown symbol, or Yahoo Finance was briefly unavailable. The holding is then valued manually or at its purchase price.

## For developers
A monorepo: a Python backend (FastAPI, PostgreSQL), a React + TypeScript frontend, and an AI assistant with a swappable model provider (Ollama locally, Gemini, OpenAI or Claude).

- [Development guide](docs/development.md): local setup, configuration, LLM providers, tests, code layout
- [Architecture](docs/architecture.md) and [data model](docs/data-model.md)
- [Specs](openspec/specs) (behaviour, source of truth) and [active changes](openspec/changes)
- [Market-data MCP server](docs/mcp-market.md)
- [Working with AI agents](docs/agents.md) and [CLAUDE.md](CLAUDE.md)

### Documentation
- [Vision](docs/vision.md), [glossary](docs/glossary.md), [roadmap](docs/roadmap.md), [history](docs/history.md)
- [CSV format](docs/csv-format.md)

## About
Coffer is built at Warsaw University of Technology for the courses _Software Engineering 1_ (specification) and _Building AI Agents in .NET_ (agent integration).

## Authors
© Bartłomiej Sokołowski, Konstanty Sobczyński, Krzysztof Wójtowicz, Krzysztof Wojczakowski @ Warsaw University of Technology

### Course groups
- **IO1** _Group 31_: Bartłomiej Sokołowski, Konstanty Sobczyński, Krzysztof Wójtowicz
- **AI Agents** _Group 4_: Bartłomiej Sokołowski, Konstanty Sobczyński, Krzysztof Wójtowicz, Krzysztof Wojczakowski
