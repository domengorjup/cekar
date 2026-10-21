## ADDED Requirements

### Requirement: Pair balances
The system SHALL compute, for every pair of users, the net amount one owes the other: for each live expense, every share of a user other than the payer is owed by that user to the payer; each live payment from X to Y reduces what X owes Y by its amount. The balances page SHALL list every pair with a non-zero net once, as "<A> owes <B> <amount>", and SHALL NOT simplify debts across pairs.

#### Scenario: Two expenses net out
- **WHEN** Ana paid €30.00 split equally with Bor, and Bor paid €10.00 split equally with Ana
- **THEN** the balances page shows "Bor owes Ana €10.00"

#### Scenario: Three members, no simplification
- **WHEN** Bor owes Ana €10.00 and Cene owes Bor €10.00
- **THEN** both pairs are listed as they are
- **AND** no "Cene owes Ana" line is invented

#### Scenario: Personal does not count
- **WHEN** the only expense is Ana's personal €8.00
- **THEN** no balance is shown

### Requirement: Own total
The balances page and the expense list header SHALL show the current user's total across all pairs ("you are owed €12.00", "you owe €3.50" or "all settled").

#### Scenario: Settled
- **WHEN** all pair nets of the current user are zero
- **THEN** the header shows "all settled"

### Requirement: Settle up
The system SHALL let a user record a payment between two members from a "Settle up" action on a pair. The amount SHALL be prefilled with the pair's full net amount and direction, and any positive amount SHALL be accepted. When the amount exceeds what is owed, the system SHALL warn before saving. Payments SHALL be editable and deletable like expenses: deleting a payment SHALL NOT ask for confirmation and SHALL offer Undo.

#### Scenario: Full settlement
- **WHEN** Bor owes Ana €10.00 and Bor settles up with the prefilled amount
- **THEN** a payment of €10.00 from Bor to Ana is recorded
- **AND** the pair no longer appears on the balances page

#### Scenario: Partial payment
- **WHEN** Bor owes Ana €10.00 and records a payment of €4.00
- **THEN** the balances page shows "Bor owes Ana €6.00"

#### Scenario: Overpayment
- **WHEN** Bor owes Ana €10.00 and enters €15.00
- **THEN** a warning is shown before saving
- **AND** after confirming, the balances page shows "Ana owes Bor €5.00"

#### Scenario: Delete a payment and undo
- **WHEN** Bor owed Ana €10.00 and settled it, and a user deletes that payment
- **THEN** the balances page shows "Bor owes Ana €10.00" and "Deleted payment · Undo"
- **AND** after Undo the pair is settled again
