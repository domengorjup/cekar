## ADDED Requirements

### Requirement: Multiple shopping lists
The system SHALL let every user create, rename, reorder and delete shopping lists. Deleting a list SHALL ask for confirmation, SHALL soft-delete the list and its items, and SHALL offer Undo. The system SHALL remember each user's last opened list and open it on start; when there is no list, it SHALL create one named "Shopping" (translated) on first use.

#### Scenario: Two lists
- **WHEN** a user creates the lists "Groceries" and "Hardware store"
- **THEN** both are shown in the list switcher in the order they were created
- **AND** each has its own items

#### Scenario: Last opened list
- **WHEN** a user opens "Hardware store" and later opens the app again
- **THEN** "Hardware store" is shown

### Requirement: Items
An item SHALL have a name (required, trimmed, 1 to 100 characters), an optional free-text quantity (up to 30 characters), an optional "for whom" member (blank means shared), and the user who added it, set automatically. Users SHALL be able to edit the name, quantity and "for whom" of an item, and delete it. Deleting an item SHALL NOT ask for confirmation and SHALL offer Undo.

#### Scenario: Add with quantity
- **WHEN** a user adds "Milk" with quantity "2 l"
- **THEN** the item "Milk · 2 l" appears at the bottom of the unchecked items
- **AND** it records that user as the one who added it

#### Scenario: Item for a person
- **WHEN** a user adds "Shampoo" for member Ana
- **THEN** the item shows Ana as the person it is for

#### Scenario: Empty name rejected
- **WHEN** a user submits an item with only spaces as name
- **THEN** nothing is added and a validation message is shown

### Requirement: Checked items section
Checking or unchecking an item SHALL take one tap. Unchecked items SHALL be shown in their own order, which users can change by dragging. Checked items SHALL be shown below them in a collapsed section titled with their count, most recently checked first. "Clear checked" SHALL remove all checked items of the list from view.

#### Scenario: Check an item
- **WHEN** a user taps the checkbox of "Milk"
- **THEN** "Milk" moves into the collapsed checked section
- **AND** the section title reads "1 checked item"

#### Scenario: Uncheck
- **WHEN** a user unchecks "Milk" in the checked section
- **THEN** it returns to the unchecked items at its previous position

#### Scenario: Clear checked
- **WHEN** a user chooses "Clear checked" on a list with three checked items
- **THEN** the checked section disappears
- **AND** the cleared items still count for suggestions

### Requirement: Suggestions from history
While a user types an item name, the system SHALL suggest at most 8 previously used item names from all lists, including cleared items and excluding deleted items, matched case- and accent-insensitively. Names starting with the typed text SHALL come before names containing it; within each group names SHALL be ranked by uses × 0.5^(days since last use / 30), then by name. Names already unchecked on the current list SHALL NOT be suggested. Each suggestion SHALL show the most recently used spelling.

#### Scenario: Frequent and recent first
- **WHEN** "Milk" was added 20 times in the last two months and "Millet" twice a year ago, and the user types "mi"
- **THEN** "Milk" is suggested before "Millet"

#### Scenario: Accent-insensitive
- **WHEN** "Čaj" was used before and the user types "caj"
- **THEN** "Čaj" is suggested

#### Scenario: Deleted mistakes are not suggested
- **WHEN** an item "Mlik" was added and then deleted, and the user types "ml"
- **THEN** "Mlik" is not suggested

### Requirement: Re-adding from a suggestion
Tapping a suggestion SHALL add that item to the current list. If an item with the same name is already unchecked on the list, the system SHALL NOT add a duplicate and SHALL highlight the existing item. If it is checked but not cleared, the system SHALL uncheck it instead of adding a new one.

#### Scenario: Suggestion of a checked item
- **WHEN** "Bread" is in the checked section and the user taps the suggestion "Bread"
- **THEN** "Bread" is unchecked and no second "Bread" is created

### Requirement: Near-live updates
While a list page is visible, the system SHALL show changes made by other users within about 5 seconds without a manual reload, by polling the list's change version. Polling SHALL pause while the page is hidden and resume, with an immediate check, when it becomes visible again. Without JavaScript the page SHALL still work with manual reloads.

#### Scenario: Partner adds an item
- **WHEN** user A has the list open and user B adds "Eggs" to it
- **THEN** "Eggs" appears on A's screen within about 5 seconds

#### Scenario: Hidden tab
- **WHEN** the list page is in a background tab
- **THEN** no version requests are sent until it becomes visible again

### Requirement: Undo delete
After a delete of a list or an item, the system SHALL show "Deleted <name> · Undo" for about 10 seconds; without JavaScript the page after the redirect SHALL show an Undo button. Undo of a list SHALL restore the list and only the items deleted together with it.

#### Scenario: Undo item delete
- **WHEN** a user deletes the item "Milk" and taps Undo
- **THEN** "Milk" is back on the list at its previous position

#### Scenario: Undo list delete
- **WHEN** a user confirms deleting the list "Groceries" and taps Undo
- **THEN** the list and its items are back

#### Scenario: Undo restores the list's items but not an item deleted before the list
- **WHEN** the item "Mlik" was deleted, then the list was deleted, and the user taps Undo
- **THEN** the list and its other items are back
- **AND** "Mlik" stays deleted
