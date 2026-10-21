"""
Shopping lists and items: CRUD, check/clear, reorder, undo, version
(design D8, D9, D17). FROZEN SIGNATURES; implemented in group 4.

Item states: unchecked (``checked_at`` is ``None``), checked (``checked_at``
set, ``cleared_at`` ``None``), cleared (``cleared_at`` set; hidden but still
used by suggestions). Unchecked items are ordered by ``position`` (new items
at the end); checked items by ``checked_at``, newest first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from cekar.models import Item, ShoppingList

LIST_NAME_MAX_LENGTH = 50
ITEM_NAME_MAX_LENGTH = 100
QUANTITY_MAX_LENGTH = 30


@dataclass(frozen=True)
class ItemView:
    """One item as shown on the list page."""

    id: str
    name: str
    quantity: str | None
    for_whom_id: str | None
    for_whom_name: str | None
    added_by_id: str
    added_by_name: str
    checked_at: datetime | None


@dataclass(frozen=True)
class ListView:
    """
    Everything the list page shows for one list.

    ``version`` is ``list_version`` at the time of reading; the page polls
    for a different value (D9).
    """

    list: ShoppingList
    unchecked: list[ItemView]
    checked: list[ItemView]
    version: int


@dataclass(frozen=True)
class AddItemResult:
    """
    Outcome of ``add_item``.

    ``outcome`` is ``"added"`` (new item), ``"existing"`` (the same name is
    already unchecked on the list; nothing changed, highlight ``item``) or
    ``"unchecked"`` (it was checked, not cleared, and is now unchecked).
    """

    item: Item
    outcome: Literal["added", "existing", "unchecked"]


def normalise_name(name: str) -> str:
    """
    Return the ``name_key`` of an item name.

    Case-folded, accents removed (Unicode NFKD without combining marks),
    whitespace collapsed to single spaces and trimmed: ``"  Čaj  Zeleni"``
    gives ``"caj zeleni"``.
    """
    raise NotImplementedError


# --- lists ---------------------------------------------------------------------

def all_lists(session: Session) -> list[ShoppingList]:
    """Return live lists by ``position``, then ``created_at``."""
    raise NotImplementedError


def get_list(session: Session, list_id: str) -> ShoppingList:
    """
    Return a live list.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def start_list(session: Session, actor_id: str, default_name: str) -> ShoppingList:
    """
    Return the list to open on start for the acting user.

    The user's ``last_list_id`` preference if that list is live, else the
    first list. When no live list exists, creates one named ``default_name``
    (the web layer passes the translated "Shopping").
    """
    raise NotImplementedError


def open_list(session: Session, actor_id: str, list_id: str) -> ShoppingList:
    """
    Return a live list and remember it as the acting user's last opened list.

    The preference is written only when it changes.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def create_list(
    session: Session, actor_id: str, name: str, *, row_id: str | None = None
) -> ShoppingList:
    """
    Create a list at the end of the order. ``name`` is trimmed.

    Raises
    ------
    ServiceError
        ``error.list.name_required``; ``error.list.name_too_long`` (``max_length``).
    """
    raise NotImplementedError


def rename_list(session: Session, actor_id: str, list_id: str, name: str) -> ShoppingList:
    """
    Rename a list. Same validation as ``create_list``.

    Raises
    ------
    ServiceError
        ``error.not_found`` and the ``create_list`` name errors.
    """
    raise NotImplementedError


def reorder_lists(session: Session, actor_id: str, list_ids: Sequence[str]) -> None:
    """
    Put lists in the given order.

    Unknown or deleted ids are ignored; live lists not named keep their
    relative order after the named ones. Only lists whose position changes
    are written.
    """
    raise NotImplementedError


def delete_list(session: Session, actor_id: str, list_id: str) -> ShoppingList:
    """
    Soft-delete a list and its live items with one ``deleted_at`` (D17).

    Returns the deleted list (for the "Deleted <name> · Undo" message).

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def restore_list(session: Session, actor_id: str, list_id: str) -> ShoppingList:
    """
    Undo ``delete_list``: the list and the items deleted with it come back;
    items deleted before the list stay deleted.

    Raises
    ------
    ServiceError
        ``error.not_found`` when the list does not exist or is not deleted.
    """
    raise NotImplementedError


def list_version(session: Session, list_id: str) -> int:
    """
    Return the largest ``seq`` over the list and all its items, tombstones
    included (so deletes change the version too). 0 for an unknown list.
    """
    raise NotImplementedError


def list_view(session: Session, list_id: str) -> ListView:
    """
    Return the list with its unchecked and checked (not cleared) live items.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


# --- items ---------------------------------------------------------------------

def get_item(session: Session, item_id: str) -> Item:
    """
    Return a live item.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def add_item(
    session: Session,
    actor_id: str,
    list_id: str,
    name: str,
    quantity: str | None = None,
    for_whom_id: str | None = None,
    *,
    row_id: str | None = None,
) -> AddItemResult:
    """
    Add an item at the end of the unchecked items, recording the adder.

    ``name`` and ``quantity`` are trimmed; a blank quantity is ``None``.
    Re-add rules (D8), matched by ``name_key`` among live, not cleared items
    of the list: an unchecked match is returned as ``"existing"`` and a
    checked match is unchecked (``"unchecked"``); in both cases ``quantity``
    and ``for_whom_id`` are ignored and the existing item is not otherwise
    changed.

    Raises
    ------
    ServiceError
        ``error.not_found`` (list); ``error.item.name_required``;
        ``error.item.name_too_long`` (``max_length``);
        ``error.item.quantity_too_long`` (``max_length``);
        ``error.item.for_whom_not_member``.
    """
    raise NotImplementedError


def update_item(
    session: Session,
    actor_id: str,
    item_id: str,
    name: str,
    quantity: str | None,
    for_whom_id: str | None,
) -> Item:
    """
    Edit an item's name, quantity and "for whom" (the edit dialog).

    Same validation as ``add_item``; no re-add rules.

    Raises
    ------
    ServiceError
        ``error.not_found`` and the ``add_item`` field errors.
    """
    raise NotImplementedError


def set_checked(session: Session, actor_id: str, item_id: str, checked: bool) -> Item:
    """
    Check (sets ``checked_at`` and ``checked_by_id``) or uncheck an item.

    Unchecking keeps ``position``, so the item returns to its old place.
    A call that changes nothing writes nothing.

    Raises
    ------
    ServiceError
        ``error.not_found`` (also for cleared items).
    """
    raise NotImplementedError


def reorder_items(
    session: Session, actor_id: str, list_id: str, item_ids: Sequence[str]
) -> None:
    """
    Put the unchecked items of a list in the given order.

    Same rules as ``reorder_lists`` (unknown ids ignored, others keep their
    relative order after the named ones).

    Raises
    ------
    ServiceError
        ``error.not_found`` (list).
    """
    raise NotImplementedError


def clear_checked(session: Session, actor_id: str, list_id: str) -> int:
    """
    Set ``cleared_at`` on all checked, not cleared items of a list.

    Returns the number of items cleared.

    Raises
    ------
    ServiceError
        ``error.not_found`` (list).
    """
    raise NotImplementedError


def checked_items(session: Session, list_id: str) -> list[Item]:
    """
    Return the live checked, not cleared items of a list, most recently
    checked first (used by "Done shopping").

    Raises
    ------
    ServiceError
        ``error.not_found`` (list).
    """
    raise NotImplementedError


def delete_item(session: Session, actor_id: str, item_id: str) -> Item:
    """
    Soft-delete an item; returns it (for "Deleted <name> · Undo").

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def restore_item(session: Session, actor_id: str, item_id: str) -> Item:
    """
    Undo ``delete_item``; the item keeps its old position.

    Raises
    ------
    ServiceError
        ``error.not_found`` when the item does not exist or is not deleted,
        or its list is deleted.
    """
    raise NotImplementedError
