# Spec Delta: accounts

## MODIFIED Requirements

### Requirement: Registration (F01)
The system SHALL let a person create an account with a display name, an e-mail address and a password. The display name SHALL be 1–50 characters after trimming and SHALL NOT contain control or format characters (Unicode Cc/Cf, e.g. newlines or bidi overrides). The account SHALL use PLN as its base currency, and the user SHALL be logged in right after registration.

#### Scenario: Successful registration
- **WHEN** a visitor submits a valid display name, a valid unregistered e-mail and a password that meets the policy
- **THEN** the account is created with that display name and base currency PLN, a session is started, and the response is 201

#### Scenario: E-mail already registered
- **WHEN** a visitor registers with an e-mail that already has an account
- **THEN** the system responds 409 "Konto z tym adresem e-mail już istnieje" and creates nothing

#### Scenario: Password breaks the policy
- **WHEN** the password is shorter than 12 characters, longer than 128, has fewer than 5 distinct characters, or is on the common-password list
- **THEN** the system responds 422 listing every broken rule in Polish

#### Scenario: Missing display name
- **WHEN** the display name is missing, blank, longer than 50 characters, or contains a control or format character
- **THEN** the system responds 422 "Imię musi mieć od 1 do 50 znaków" and creates nothing

### Requirement: Account deletion (N09)
A logged-in user SHALL be able to permanently delete their account and all their data (transactions, portfolio, profile, opening balance) after confirming with their password.

#### Scenario: Confirmed deletion
- **WHEN** the user confirms deletion with the correct password
- **THEN** all user data is deleted, the session ends, the response is 204, and the account can no longer log in

#### Scenario: Wrong password on deletion
- **WHEN** the password does not match
- **THEN** the system responds 403 and deletes nothing

## ADDED Requirements

### Requirement: Display name
Every account SHALL have a display name, and `GET /api/auth/me` SHALL return it. A logged-in user SHALL be able to change it with `PATCH /api/auth/me`, using the same 1–50 character rule as registration. The navbar SHALL show the display name, not the e-mail.

#### Scenario: Change display name
- **WHEN** a logged-in user sends a valid new display name
- **THEN** the name is saved, the response contains it, and the navbar shows it

#### Scenario: Invalid display name on change
- **WHEN** the new display name is blank, longer than 50 characters, or contains a control or format character
- **THEN** the system responds 422 "Imię musi mieć od 1 do 50 znaków" and keeps the old name

#### Scenario: Accounts from before display names
- **WHEN** the migration that adds display names runs on a database with existing accounts
- **THEN** every existing account and all of its data are deleted, and the column is created NOT NULL
