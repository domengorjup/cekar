## ADDED Requirements

### Requirement: English and Slovenian
Every user-visible text, including validation messages, SHALL be available in English and Slovenian. English SHALL be the fallback for a missing translation. Slovenian plural forms (one, two, few, other) SHALL be used where a count is shown.

#### Scenario: Slovenian plural
- **WHEN** the language is Slovenian and two items are checked
- **THEN** the checked section title uses the dual form ("2 označena izdelka")

#### Scenario: Catalogs complete
- **WHEN** the test suite runs
- **THEN** both catalogs contain the same keys with the same placeholders, and every key used in code and templates exists

### Requirement: Language per user
Each user SHALL be able to choose English or Slovenian from the user menu; the choice SHALL be stored with the user and apply on every device. When a user has not chosen, the language SHALL be the best match of the request's `Accept-Language` header among Slovenian and English, else English.

#### Scenario: Default from the browser
- **WHEN** a user who has not chosen a language sends `Accept-Language: sl-SI,sl;q=0.9,en;q=0.8`
- **THEN** pages are shown in Slovenian

#### Scenario: Explicit choice wins
- **WHEN** that user chooses English
- **THEN** pages are shown in English on all devices, whatever the browser language

### Requirement: Locale formatting
Amounts and dates SHALL be formatted for the active language: Slovenian `12,50 €` and `21. 10. 2026`; English `€12.50` and `21 Oct 2026`. Amount input SHALL accept a decimal comma or point in both languages.

#### Scenario: Amount display
- **WHEN** an expense of 1250 cents is shown in Slovenian
- **THEN** it reads `12,50 €`
