## ADDED Requirements

### Requirement: Expense records
An expense SHALL have a title, an amount in euro (stored as integer cents, greater than zero, at most two decimals), a date (default today), exactly one payer, and a split method with its shares. Amount input SHALL accept a decimal comma or a decimal point. Users SHALL be able to edit and delete any expense. Deleting SHALL NOT ask for confirmation and SHALL offer Undo.

#### Scenario: Decimal comma
- **WHEN** a user enters the amount "12,5"
- **THEN** the expense is stored as 1250 cents

#### Scenario: Invalid amount
- **WHEN** a user enters "0", "-3" or "1,234"
- **THEN** the expense is not saved and a validation message is shown

### Requirement: Paid-by dropdown
The add and edit forms SHALL always show "Paid by" as a dropdown of members. On the add form it SHALL default to the current user when that user is a member, otherwise to the first member in display order.

#### Scenario: Default payer
- **WHEN** member Ana opens "Add expense"
- **THEN** "Paid by" shows Ana

#### Scenario: Someone else paid
- **WHEN** Ana records an expense and selects Bor as payer
- **THEN** the expense is saved with Bor as payer

### Requirement: One-tap split choices
The add form SHALL show the split choices "Split equally" (default), "For <person>", "Personal" and "Exact amounts" directly under the amount, each selectable with one tap. With exactly two members, "For <person>" SHALL name the member who is not the payer and SHALL follow changes of the payer. With more than two members it SHALL ask which member (excluding the payer).

#### Scenario: Two members
- **WHEN** members are Ana and Bor and the payer is Ana
- **THEN** the choice reads "For Bor"
- **AND** after changing the payer to Bor it reads "For Ana"

### Requirement: Equal split with deterministic rounding
"Split equally" SHALL divide the amount among the chosen participants (default: all members). Each participant's share SHALL be the amount divided by the number of participants, rounded down to whole cents; the remaining cents SHALL go one each to the payer first, if the payer participates, then to the other participants in member display order. Shares SHALL always sum to the amount.

#### Scenario: Odd cent with two members
- **WHEN** Ana pays €10.01 split equally between Ana and Bor
- **THEN** Ana's share is €5.01 and Bor's share is €5.00
- **AND** Bor owes Ana €5.00

#### Scenario: Three members
- **WHEN** Ana pays €10.00 split equally among Ana, Bor and Cene (in that member order)
- **THEN** the shares are Ana €3.34, Bor €3.33, Cene €3.33

#### Scenario: Payer not participating
- **WHEN** Ana pays €10.01 split equally between Bor and Cene only
- **THEN** Bor's share is €5.01 and Cene's share is €5.00

### Requirement: Exact amounts
"Exact amounts" SHALL let the user enter an amount per member. The form SHALL show the difference between the total and the sum of the entered amounts, and the system SHALL NOT save until the difference is zero. Members with an empty or zero amount SHALL have no share.

#### Scenario: Amounts do not add up
- **WHEN** the total is €30.00 and the entered amounts are €10.00 and €15.00
- **THEN** the form shows "€5.00 left" and does not save

### Requirement: For another person
"For <person>" SHALL record a single share of the full amount for that person, so that the person owes the payer the full amount.

#### Scenario: Paid for the partner
- **WHEN** Ana pays €24.90 "For Bor"
- **THEN** Bor owes Ana €24.90 from this expense

### Requirement: Personal expense
"Personal" SHALL record a single share of the full amount for the payer, so that nobody owes anything. Personal expenses SHALL appear in the expense list like any other expense, marked "Personal".

#### Scenario: Personal purchase
- **WHEN** Ana records €8.00 as "Personal"
- **THEN** the expense appears in the list marked "Personal"
- **AND** no balance changes

### Requirement: Expense list
The system SHALL show all expenses and payments newest first, grouped by month, each with title, amount, payer, date, and the current user's part in it ("you owe €5.00", "you lent €5.00", "personal", "not involved"). Expenses created by one shopping trip SHALL be shown as ONE collapsed row (trip badge, list name, trip total) that expands to show the individual expenses, each with the same details as an ordinary row.

#### Scenario: Trip as one collapsed row
- **WHEN** a trip on the list "Groceries" created three expenses totalling €50.00
- **THEN** the expense list shows one collapsed row with a trip badge, "Groceries" and "€50.00"
- **AND** tapping the row shows the three individual expenses

#### Scenario: Viewer's part
- **WHEN** Bor views an expense where Ana paid €10.00 split equally between them
- **THEN** the row shows "you owe €5.00"

### Requirement: Undo expense delete
After an expense is deleted, the system SHALL show "Deleted <title> · Undo" for about 10 seconds; without JavaScript the page after the redirect SHALL show an Undo button. Undo SHALL restore the expense and its shares, and balances SHALL include them again.

#### Scenario: Delete and undo
- **WHEN** a user deletes the expense "Pizza" without any confirmation dialog and taps Undo
- **THEN** "Pizza" is back in the expense list with its shares
- **AND** the balances include it again

#### Scenario: Undo without JavaScript
- **WHEN** a user without JavaScript deletes an expense
- **THEN** the page after the redirect shows an Undo button
