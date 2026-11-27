# Spec Delta

## ADDED Requirements

### Requirement: Investment profile (F30)
A user SHALL be able to save an investment profile (`PUT /api/profile`) with an investment horizon (up to 2 years / 2–5 years / over 5 years), a risk tolerance (low / medium / high) and at least one preferred asset class, and read it back (`GET /api/profile`, null when not set).

#### Scenario: Save and read back
- **WHEN** the user saves a complete profile
- **THEN** `GET /api/profile` returns the saved horizon, risk tolerance and asset classes

#### Scenario: Incomplete profile
- **WHEN** the horizon or risk tolerance is missing or no asset class is selected
- **THEN** the system responds 422 and keeps the previous profile
