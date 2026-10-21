## ADDED Requirements

### Requirement: Automatic user registration
The system SHALL register a user automatically on the first request that identifies an unknown HA user, storing the HA user id, user name and display name. On later requests it SHALL update the stored display name when the header value has changed. A newly registered user SHALL NOT be an expense member.

#### Scenario: First visit of an HA user
- **WHEN** a proxied request carries an `X-Remote-User-Id` that is not yet known
- **THEN** a user with that HA id and display name is created
- **AND** the user is not a member

#### Scenario: Renamed in HA
- **WHEN** a known user's request carries a different `X-Remote-User-Display-Name`
- **THEN** the stored display name is updated

### Requirement: Expense membership
The system SHALL keep a member flag per user. Only members SHALL be selectable as payer, as participant of a split, as "for whom" of an expense or item, and in settle up. Every user, member or not, SHALL be able to use all shopping lists.

#### Scenario: Non-member uses lists
- **WHEN** a non-member adds, checks and clears items
- **THEN** the changes are saved and attributed to that user

#### Scenario: Non-member not offered as payer
- **WHEN** the expense form is shown
- **THEN** the paid-by dropdown and the participant choices list members only

### Requirement: Settings page for membership
The system SHALL provide a Settings page, available to every user, that lists all users with a switch "Member of shared expenses". Turning the switch on SHALL record the time it became a member (used for display order). In standalone mode and in picker fallback, Settings SHALL also allow adding a person by name; people added this way SHALL start as members.

#### Scenario: Tick a member
- **WHEN** a user turns on "Member of shared expenses" for another user
- **THEN** that user appears in the paid-by dropdown and the split choices

#### Scenario: Add a person in standalone mode
- **WHEN** in standalone mode a user adds the person "Ana" in Settings
- **THEN** Ana appears in the "Who are you?" picker and as a member

### Requirement: Removing a member keeps history
When a member is turned off, the system SHALL keep all their existing expense shares, expenses paid and payments, and SHALL keep showing any non-zero balance that involves them until it is settled. Turning a member off SHALL NOT be blocked. When that balance is not zero, the system SHALL warn before turning the member off, and the warning SHALL show the amount.

#### Scenario: Former member with open balance
- **WHEN** a member who owes 12,00 € is turned off
- **THEN** a warning showing "12,00 €" is shown first
- **AND** after the user confirms the warning the member is turned off
- **AND** the balance "owes 12,00 €" is still shown on the balances page
- **AND** settle up for that pair is still possible

### Requirement: At least two members for expenses
The system SHALL require at least two members before an expense can be saved. With fewer members the expense pages SHALL show a hint with a button to Settings instead of the form.

#### Scenario: Only one member
- **WHEN** only one user is a member and someone opens "Add expense"
- **THEN** a hint to tick members in Settings is shown instead of the form
