# transactions Specification

## Purpose
Recording money flows: manual transactions, editing and deletion, CSV import with preview, de-duplication and automatic categorization. Covers F03–F08 and N05 (former UC-02, UC-03, UC-10). The CSV file format is described in `docs/csv-format.md`.

## Requirements

### Requirement: Manual transaction entry (F03)
A user SHALL be able to add a transaction with a date, an amount in PLN, a description and exactly one category. A positive amount is income and a negative amount is an expense.

#### Scenario: Valid transaction
- **WHEN** the user submits a date, a non-zero amount with at most 2 decimal places, a description and a known category
- **THEN** the transaction is saved with source `manual` and the response is 201

#### Scenario: Invalid amount or date
- **WHEN** the amount is not a number, is zero, has more than 2 decimal places, exceeds NUMERIC(14,2), or the date is missing
- **THEN** the system responds 422 with Polish field errors and saves nothing

#### Scenario: Unknown category
- **WHEN** the category id does not exist
- **THEN** the system responds 422 "Nieznana kategoria"

### Requirement: Categories
Categories SHALL be a global system list available at `GET /api/categories`. Each category SHALL be flagged as in-budget or not; "Przelewy własne" (own transfers) and "Inwestycje" (investments) are outside the budget. The default category is "Inne".

#### Scenario: Listing categories
- **WHEN** a logged-in user requests the categories
- **THEN** the system returns every category with its id, name and in-budget flag

### Requirement: Listing transactions
A user SHALL be able to list their own transactions, optionally limited to one month (`GET /api/transactions?month=YYYY-MM`). The UI SHALL offer filters (type, category, source) and sorting (date or amount).

#### Scenario: Month filter
- **WHEN** the user lists transactions for a month
- **THEN** only that user's transactions dated in that month are returned

### Requirement: Edit and delete (F06, F08)
A user SHALL be able to change the date, amount, description and category of their transaction (`PATCH /api/transactions/{id}`) and delete it after confirmation (`DELETE /api/transactions/{id}`). Budget summaries SHALL reflect the change to the grosz (N04).

#### Scenario: Inline edit
- **WHEN** the user edits one transaction in its list row and saves
- **THEN** the changed fields are validated like a new transaction and stored

#### Scenario: Delete with confirmation
- **WHEN** the user confirms deletion in the confirm dialog
- **THEN** the transaction is deleted and the response is 204

#### Scenario: Transaction not found
- **WHEN** the id does not exist or belongs to another user
- **THEN** the system responds 404 "Nie znaleziono transakcji"

### Requirement: CSV import with preview (F04)
A user SHALL be able to upload a CSV bank statement (max 1 MB, bank chosen from `GET /api/imports/banks`). The system SHALL create a preview draft (`POST /api/imports`) showing new rows, duplicates and invalid rows, and save nothing until the user commits it (`POST /api/imports/{id}/commit`). Drafts SHALL expire and expired drafts SHALL be removed.

#### Scenario: Preview and commit
- **WHEN** the user uploads a valid file and commits the preview
- **THEN** only the new rows are saved as transactions with source `import`, and the response reports how many were imported

#### Scenario: Invalid file
- **WHEN** the file is too large, unsupported, empty, or lacks required columns
- **THEN** the system responds 422 with a Polish message (e.g. "Plik jest za duży (maks. 1 MB)") and saves nothing

#### Scenario: Invalid rows
- **WHEN** some rows are invalid (bad amount, unsupported currency)
- **THEN** those rows are listed with their 0-based index and error and are not imported, while the other rows stay importable

#### Scenario: Cancel
- **WHEN** the user cancels the preview (`DELETE /api/imports/{id}`)
- **THEN** nothing is saved

#### Scenario: Double commit
- **WHEN** the same draft is committed twice, including concurrently
- **THEN** the transactions are saved only once

### Requirement: Import de-duplication (F05)
A row SHALL be treated as a duplicate when a saved transaction has the same date, amount and description (whitespace-normalized, case-insensitive). The comparison SHALL be a multiset limited to the file's date range.

#### Scenario: Re-import of the same file
- **WHEN** the user imports a file that was already imported
- **THEN** every row is marked as a duplicate and nothing new is saved

#### Scenario: Identical rows in one file
- **WHEN** a file has two identical rows and the database has one matching transaction
- **THEN** one row is new and one is a duplicate

### Requirement: Automatic categorization (F07, N05)
The system SHALL assign a category to each imported row: first by an exact match with a description the user categorized before (learning from the user's own corrections, F08), then by keyword rules. A row with no match SHALL get the default category and a "to review" flag. Keyword rules SHALL categorize at least 80% of the 200-transaction test set correctly (test `tests/imports/test_n05.py`).

#### Scenario: Learned category
- **WHEN** an imported description exactly matches one the user previously re-categorized
- **THEN** the row gets the user's chosen category

#### Scenario: No match
- **WHEN** neither a learned description nor a keyword matches
- **THEN** the row gets the default category and is flagged for review
