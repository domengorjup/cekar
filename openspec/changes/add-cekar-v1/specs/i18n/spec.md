## ADDED Requirements

### Requirement: English only in v1.0, ready for more languages
Version 1.0 SHALL ship the English catalog only, with no language switch in the UI and no per-user language preference. Every user-visible text, including validation messages, SHALL come from the message catalog through `t()` and `tn()`, so that another language can be added later by adding a catalog. `tn()` SHALL support plural forms; only the English forms (one, other) are required now.

#### Scenario: English plural
- **WHEN** two items are checked
- **THEN** the checked section title reads "2 checked items"

#### Scenario: Catalog is complete
- **WHEN** the test suite runs
- **THEN** every key used in code and templates exists in the English catalog, and every plural key has the `one` and `other` forms

#### Scenario: No language controls
- **WHEN** a user opens the user menu or Settings
- **THEN** no language switch is shown

### Requirement: Formatting
Amounts and dates SHALL be formatted in the English style: `€12.50` (symbol first, decimal point) and `21 Oct 2026`. Amount input SHALL accept a decimal comma or point.

#### Scenario: Amount display
- **WHEN** an expense of 1250 cents is shown
- **THEN** it reads `€12.50`

#### Scenario: Amount input with comma
- **WHEN** a user enters `12,5` as an amount
- **THEN** it is read as 12 euro and 50 cents
