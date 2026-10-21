## ADDED Requirements

### Requirement: UUID identifiers
Every table that holds user data SHALL use a UUID as its primary key, so that a later client can create rows offline with its own ids. Creating a row with an id that already exists SHALL NOT create a second row.

#### Scenario: Repeated create
- **WHEN** the service layer is asked twice to create an item with the same id
- **THEN** only one item exists

### Requirement: Timestamps and tombstones
Every user-data row SHALL carry `created_at`, `updated_at` and `deleted_at` (UTC). Every write SHALL update `updated_at`. Deleting SHALL set `deleted_at` instead of removing the row, and deleting a parent (a list, an expense) SHALL also set `deleted_at` on its children. Rows with `deleted_at` set SHALL NOT appear in any page or computation.

#### Scenario: Deleted expense
- **WHEN** an expense is deleted
- **THEN** its row and its shares remain in the database with `deleted_at` set
- **AND** it no longer appears in the list or in any balance

### Requirement: Change sequence
The system SHALL keep one global, strictly increasing change counter. Every write SHALL store the next counter value in the written row's `seq` column, within the same transaction, so that all rows changed after a cursor N can be found with `seq > N`.

#### Scenario: Changes since a cursor
- **WHEN** the counter is at 100 and a user checks an item and adds an expense
- **THEN** exactly those rows (and the expense's shares) have `seq` greater than 100

#### Scenario: List version
- **WHEN** an item on a list changes
- **THEN** the list's version (the largest `seq` of the list and its items) increases

### Requirement: Writes only through the service layer
All creates, updates and deletes SHALL go through the service functions, which take plain values and the acting user's id. Web routes SHALL NOT write to the database directly.

#### Scenario: Route test
- **WHEN** the test suite runs
- **THEN** a check confirms that no module under `web/` calls the session's add, delete or commit methods

### Requirement: Restore
Restoring a deleted row (undo) SHALL clear `deleted_at` on the row and on those children whose `deleted_at` equals the parent's, that is, children deleted in the same deletion. Children deleted earlier SHALL stay deleted. Restore SHALL update `updated_at` and take the next `seq` on every row it changes.

#### Scenario: Restore an expense
- **WHEN** a deleted expense is restored
- **THEN** the expense and its shares have no `deleted_at`
- **AND** their `updated_at` and `seq` are newer than before the restore

#### Scenario: Restore a list
- **WHEN** an item was deleted, then its list was deleted, and the list is restored
- **THEN** the list and its other items are live again
- **AND** the earlier-deleted item keeps its `deleted_at`
