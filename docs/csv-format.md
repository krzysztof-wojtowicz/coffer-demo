# Test CSV format ("Coffer Test Bank")

A fictional format for developing and testing import before real banks are supported. All data in the repo is fictional. Example: [`data/fixtures/csv/testbank-2026-10.csv`](../data/fixtures/csv/testbank-2026-10.csv). Import behaviour is specified in [`openspec/specs/transactions`](../openspec/specs/transactions/spec.md).

## File format

| Property | Value |
|---|---|
| Encoding | UTF-8 (no BOM) |
| Separator | `;` |
| Header rows | 1 |
| Date | `DD.MM.YYYY` |
| Amount | decimal comma, space as thousands separator (`-1 234,56`); negative = expense |
| Currency | ISO 4217 code (`PLN`, `EUR`, …) |

| Column | Use in import |
|---|---|
| `Data operacji` | transaction date |
| `Data księgowania` | ignored |
| `Opis` | description (may contain names and account numbers) |
| `Kwota` | amount in the original currency |
| `Waluta` | original currency; only `PLN` is supported now, other rows get the error "Waluta … nie jest jeszcze obsługiwana" (daily-rate conversion is planned) |
| `Saldo po operacji` | ignored |

## De-duplication and categorization
- **Duplicate (F05):** a row with the same date, amount and description (whitespace-normalized, case-insensitive) as a saved transaction. Only the file's date range is compared, as a multiset: two identical rows in the file and one in the database give one new row and one duplicate.
- **Category (F07):** first an exact match with a description the user categorized before (their own corrections, F08), then keyword rules; a row with no match gets the default category and a "to review" flag. Rule accuracy (N05, at least 80%) is checked by a test on 200 fictional transactions.

## Bank configuration
The importer has no class per bank, only configuration. Real banks will be added as more entries:

```toml
[banks.testbank]
name = "Coffer Test Bank"
encoding = "utf-8"
delimiter = ";"
skip_rows = 1
date_format = "%d.%m.%Y"
decimal_separator = ","
thousands_separator = " "
columns = { date = "Data operacji", description = "Opis", amount = "Kwota", currency = "Waluta" }
```

## Cases in the sample file
- two identical public-transport tickets on the same day (multiset de-duplication, F05),
- a transaction in EUR (currency conversion),
- a transfer with a person's name and account number in the description (anonymization),
- an own transfer and a brokerage top-up (categories outside the budget),
- income: salary and a refund from a friend.
