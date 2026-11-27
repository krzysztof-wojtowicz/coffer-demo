# Spec Delta

## MODIFIED Requirements

### Requirement: Account deletion (N09)
A logged-in user SHALL be able to permanently delete their account and all their data (transactions, portfolio, profile, limits, opening balance) after confirming with their password.

#### Scenario: Confirmed deletion
- **WHEN** the user confirms deletion with the correct password
- **THEN** all user data is deleted, the session ends, the response is 204, and the account can no longer log in

#### Scenario: Wrong password on deletion
- **WHEN** the password does not match
- **THEN** the system responds 403 and deletes nothing
