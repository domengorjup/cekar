## ADDED Requirements

### Requirement: Done shopping form
A list with at least one checked item SHALL offer "Done shopping". It SHALL open a form with the receipt total (required), the date (default today), "Paid by" (member dropdown, default the current user if a member, else the first member), a price field for every checked item that has a "for whom" member, and the remaining checked items listed as shared. The sum of the entered prices SHALL NOT exceed the total; a blank price SHALL make that item shared.

#### Scenario: Form contents
- **WHEN** the checked items are "Milk" (shared), "Shampoo" (for Bor) and "Razor" (for Ana), and Ana opens "Done shopping"
- **THEN** the form shows price fields for "Shampoo" and "Razor", "Milk" as shared, and "Paid by" set to Ana

#### Scenario: Prices exceed the total
- **WHEN** the total is €10.00 and the entered prices sum to €12.00
- **THEN** the form is not saved and a validation message is shown

### Requirement: Expenses created from a trip
Confirming "Done shopping" SHALL, in one transaction, record a shopping trip and create: for each member other than the payer with priced items, one "for <person>" expense with the sum of that person's prices; if the payer has priced items, one personal expense with their sum; and if the remainder (total minus all entered prices) is above zero, one equal-split expense among all members. Expenses with a zero amount SHALL NOT be created. All created expenses SHALL be linked to the trip. The expense for one person's priced items SHALL be titled "<list name>: <item names>" (the names of that person's priced items, comma-separated); the equal-split expense SHALL be titled with the list name.

#### Scenario: Mixed receipt
- **WHEN** the members are Ana and Bor and Ana pays a total of €50.00 with "Shampoo" for Bor priced €6.00 and "Razor" for Ana priced €4.00
- **THEN** a €6.00 "for Bor" expense titled "<list name>: Shampoo", a €4.00 personal expense for Ana titled "<list name>: Razor" and a €40.00 equal-split expense are created
- **AND** the balances page shows "Bor owes Ana €26.00"

#### Scenario: Only shared items
- **WHEN** no checked item has a "for whom" and Bor enters a total of €31.25
- **THEN** exactly one equal-split expense of €31.25 paid by Bor is created

#### Scenario: Everything priced
- **WHEN** the entered prices sum exactly to the total
- **THEN** no equal-split expense is created

### Requirement: Checked items cleared after the trip
After the trip is saved, the system SHALL clear all checked items of the list, so they disappear from the list and still feed suggestions. Unchecked items SHALL stay on the list.

#### Scenario: Unchecked items stay
- **WHEN** a trip is saved on a list with two checked and three unchecked items
- **THEN** the list shows the three unchecked items and no checked section

### Requirement: Trip without enough members
When fewer than two members exist, "Done shopping" SHALL only clear the checked items, after a confirmation that explains no expense will be created.

#### Scenario: Single member household
- **WHEN** only one member exists and a user confirms "Done shopping"
- **THEN** the checked items are cleared and no expense is created
