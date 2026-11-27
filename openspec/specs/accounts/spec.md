# accounts Specification

## Purpose
User accounts and sessions: registration, login, logout, password change, and permanent account deletion. Every user sees only their own data. Covers F01, F02, N01, N02, N09 (former UC-01, UC-08, UC-09).

## Requirements

### Requirement: Registration (F01)
The system SHALL let a person create an account with an e-mail address and a password. The account SHALL use PLN as its base currency, and the user SHALL be logged in right after registration.

#### Scenario: Successful registration
- **WHEN** a visitor submits a valid, unregistered e-mail and a password that meets the policy
- **THEN** the account is created with base currency PLN, a session is started, and the response is 201

#### Scenario: E-mail already registered
- **WHEN** a visitor registers with an e-mail that already has an account
- **THEN** the system responds 409 "Konto z tym adresem e-mail już istnieje" and creates nothing

#### Scenario: Password breaks the policy
- **WHEN** the password is shorter than 12 characters, longer than 128, has fewer than 5 distinct characters, or is on the common-password list
- **THEN** the system responds 422 listing every broken rule in Polish

### Requirement: Password storage (N01)
Passwords SHALL be stored only as salted hashes (Argon2id). No plain-text password SHALL be stored or logged anywhere.

#### Scenario: Stored credentials
- **WHEN** an account is created or its password is changed
- **THEN** only the Argon2id hash is persisted

### Requirement: Login and logout
The system SHALL start a session cookie (`coffer_session`) valid for `session_ttl_days` (default 14) after a correct login, and SHALL invalidate it immediately on logout. Logout from all devices SHALL invalidate every session of the user.

#### Scenario: Wrong credentials
- **WHEN** the e-mail or password is wrong
- **THEN** the system responds 401 with the single message "Nieprawidłowy e-mail lub hasło", in constant time whether or not the account exists

#### Scenario: Logout
- **WHEN** a logged-in user logs out
- **THEN** the session is invalidated and later requests with that cookie are refused

#### Scenario: Expired session
- **WHEN** a request carries a session older than the TTL
- **THEN** the request is refused with 401 and the frontend redirects to the login page

### Requirement: Access control (F02, N02)
Every endpoint except `/api/health` and `/api/auth/{register,login,logout}` SHALL require a valid session, and every query SHALL be filtered by the current user. A resource owned by another user SHALL be reported as not found.

#### Scenario: No session
- **WHEN** a request without a valid session hits a protected endpoint
- **THEN** the system responds 401 and returns no financial data

#### Scenario: Another user's resource
- **WHEN** a user requests a resource id that belongs to someone else
- **THEN** the system responds 404

### Requirement: Rate limiting of credential endpoints
Register, login, password change and account deletion SHALL be rate limited and respond 429 when the limit is exceeded.

#### Scenario: Too many attempts
- **WHEN** a client exceeds the attempt limit on a credential endpoint
- **THEN** the system responds 429 without checking the credentials

### Requirement: Password change
A logged-in user SHALL be able to change their password after confirming the current one.

#### Scenario: Wrong current password
- **WHEN** the current password does not match
- **THEN** the system responds 403 and keeps the old password

### Requirement: Account deletion (N09)
A logged-in user SHALL be able to permanently delete their account and all their data (transactions, portfolio, profile, limits, opening balance) after confirming with their password.

#### Scenario: Confirmed deletion
- **WHEN** the user confirms deletion with the correct password
- **THEN** all user data is deleted, the session ends, the response is 204, and the account can no longer log in

#### Scenario: Wrong password on deletion
- **WHEN** the password does not match
- **THEN** the system responds 403 and deletes nothing
