"""
Shopping lists and items: CRUD, check/clear, reorder, undo, version
(design D8, D9, D17). FROZEN SIGNATURES; implemented in group 4.

Item states: unchecked (``checked_at`` is ``None``), checked (``checked_at``
set, ``cleared_at`` ``None``), cleared (``cleared_at`` set; hidden but still
used by suggestions). Unchecked items are ordered by ``position`` (new items
at the end); checked items by ``checked_at``, newest first.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cekar.models import Item, ShoppingList, User, UserPreference, utc_now
from cekar.services import ServiceError, sync

LIST_NAME_MAX_LENGTH = 50
ITEM_NAME_MAX_LENGTH = 100
QUANTITY_MAX_LENGTH = 30

# Key of the ``user_preference`` row (same value as ``members.LAST_LIST_ID``).
LAST_LIST_ID = "last_list_id"


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
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


# --- helpers -------------------------------------------------------------------

def _clean_list_name(name: str) -> str:
    """Return the trimmed list name or raise the name error."""
    name = name.strip()
    if not name:
        raise ServiceError("error.list.name_required")
    if len(name) > LIST_NAME_MAX_LENGTH:
        raise ServiceError("error.list.name_too_long", max_length=LIST_NAME_MAX_LENGTH)
    return name


def _clean_item_fields(
    session: Session, name: str, quantity: str | None, for_whom_id: str | None
) -> tuple[str, str | None]:
    """Validate and trim the item fields; return ``(name, quantity)``."""
    name = name.strip()
    if not name:
        raise ServiceError("error.item.name_required")
    if len(name) > ITEM_NAME_MAX_LENGTH:
        raise ServiceError("error.item.name_too_long", max_length=ITEM_NAME_MAX_LENGTH)
    quantity = (quantity or "").strip() or None
    if quantity is not None and len(quantity) > QUANTITY_MAX_LENGTH:
        raise ServiceError("error.item.quantity_too_long", max_length=QUANTITY_MAX_LENGTH)
    if for_whom_id is not None:
        user = session.get(User, for_whom_id)
        if user is None or user.deleted_at is not None or not user.is_member:
            raise ServiceError("error.item.for_whom_not_member")
    return name, quantity


def _next_position(session: Session, column, *conditions) -> int:
    """Return one more than the largest live position under ``conditions``."""
    query = select(func.max(column)).where(*conditions)
    highest = session.scalar(query)
    return 0 if highest is None else highest + 1


def _apply_order(rows: list, ids: Sequence[str], session: Session) -> None:
    """
    Renumber ``rows`` (in their current order) so the named ids come first.

    Only rows whose position changes are written.
    """
    by_id = {row.id: row for row in rows}
    named = [by_id[i] for i in dict.fromkeys(ids) if i in by_id]
    named_ids = {row.id for row in named}
    ordered = named + [row for row in rows if row.id not in named_ids]
    for position, row in enumerate(ordered):
        if row.position != position:
            row.position = position
            sync.touch(row, session)


def _unchecked_items(session: Session, list_id: str) -> list[Item]:
    query = sync.live(
        select(Item).where(
            Item.list_id == list_id, Item.checked_at.is_(None), Item.cleared_at.is_(None)
        )
    ).order_by(Item.position, Item.created_at)
    return list(session.scalars(query))


def _checked_items(session: Session, list_id: str) -> list[Item]:
    query = sync.live(
        select(Item).where(
            Item.list_id == list_id, Item.checked_at.is_not(None), Item.cleared_at.is_(None)
        )
    ).order_by(Item.checked_at.desc(), Item.created_at.desc())
    return list(session.scalars(query))


# --- lists ---------------------------------------------------------------------

def all_lists(session: Session) -> list[ShoppingList]:
    """Return live lists by ``position``, then ``created_at``."""
    query = sync.live(select(ShoppingList)).order_by(
        ShoppingList.position, ShoppingList.created_at
    )
    return list(session.scalars(query))


def get_list(session: Session, list_id: str) -> ShoppingList:
    """
    Return a live list.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    shopping = session.get(ShoppingList, list_id)
    if shopping is None or shopping.deleted_at is not None:
        raise ServiceError("error.not_found")
    return shopping


def start_list(session: Session, actor_id: str, default_name: str) -> ShoppingList:
    """
    Return the list to open on start for the acting user.

    The user's ``last_list_id`` preference if that list is live, else the
    first list. When no live list exists, creates one named ``default_name``
    (the web layer passes the translated "Shopping").
    """
    preference = _preference(session, actor_id)
    if preference is not None and preference.value:
        remembered = session.get(ShoppingList, preference.value)
        if remembered is not None and remembered.deleted_at is None:
            return remembered
    lists = all_lists(session)
    if lists:
        return lists[0]
    return create_list(session, actor_id, default_name)


def _preference(session: Session, user_id: str) -> UserPreference | None:
    query = sync.live(select(UserPreference)).where(
        UserPreference.user_id == user_id, UserPreference.key == LAST_LIST_ID
    )
    return session.scalars(query).first()


def open_list(session: Session, actor_id: str, list_id: str) -> ShoppingList:
    """
    Return a live list and remember it as the acting user's last opened list.

    The preference is written only when it changes.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    shopping = get_list(session, list_id)
    preference = _preference(session, actor_id)
    if preference is None:
        sync.touch(
            UserPreference(user_id=actor_id, key=LAST_LIST_ID, value=list_id), session
        )
    elif preference.value != list_id:
        preference.value = list_id
        sync.touch(preference, session)
    return shopping


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
    if row_id is not None:
        existing = session.get(ShoppingList, row_id)
        if existing is not None:
            return existing
    name = _clean_list_name(name)
    position = _next_position(
        session, ShoppingList.position, ShoppingList.deleted_at.is_(None)
    )
    shopping = ShoppingList(id=row_id, name=name, position=position)
    sync.touch(shopping, session)
    return shopping


def rename_list(session: Session, actor_id: str, list_id: str, name: str) -> ShoppingList:
    """
    Rename a list. Same validation as ``create_list``.

    Raises
    ------
    ServiceError
        ``error.not_found`` and the ``create_list`` name errors.
    """
    shopping = get_list(session, list_id)
    name = _clean_list_name(name)
    if shopping.name != name:
        shopping.name = name
        sync.touch(shopping, session)
    return shopping


def reorder_lists(session: Session, actor_id: str, list_ids: Sequence[str]) -> None:
    """
    Put lists in the given order.

    Unknown or deleted ids are ignored; live lists not named keep their
    relative order after the named ones. Only lists whose position changes
    are written.
    """
    _apply_order(all_lists(session), list_ids, session)


def delete_list(session: Session, actor_id: str, list_id: str) -> ShoppingList:
    """
    Soft-delete a list and its live items with one ``deleted_at`` (D17).

    Returns the deleted list (for the "Deleted <name> · Undo" message).

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    shopping = get_list(session, list_id)
    sync.soft_delete(shopping, session)
    return shopping


def restore_list(session: Session, actor_id: str, list_id: str) -> ShoppingList:
    """
    Undo ``delete_list``: the list and the items deleted with it come back;
    items deleted before the list stay deleted.

    Raises
    ------
    ServiceError
        ``error.not_found`` when the list does not exist or is not deleted.
    """
    shopping = session.get(ShoppingList, list_id)
    if shopping is None or shopping.deleted_at is None:
        raise ServiceError("error.not_found")
    sync.restore(shopping, session)
    return shopping


def list_version(session: Session, list_id: str) -> int:
    """
    Return the largest ``seq`` over the list and all its items, tombstones
    included (so deletes change the version too). 0 for an unknown list.
    """
    list_seq = session.scalar(select(func.max(ShoppingList.seq)).where(ShoppingList.id == list_id))
    item_seq = session.scalar(select(func.max(Item.seq)).where(Item.list_id == list_id))
    return max(list_seq or 0, item_seq or 0)


def _item_view(session: Session, item: Item) -> ItemView:
    for_whom = session.get(User, item.for_whom_id) if item.for_whom_id else None
    added_by = session.get(User, item.added_by_id)
    return ItemView(
        id=item.id,
        name=item.name,
        quantity=item.quantity,
        for_whom_id=item.for_whom_id,
        for_whom_name=for_whom.display_name if for_whom else None,
        added_by_id=item.added_by_id,
        added_by_name=added_by.display_name,
        checked_at=item.checked_at,
    )


def list_view(session: Session, list_id: str) -> ListView:
    """
    Return the list with its unchecked and checked (not cleared) live items.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    shopping = get_list(session, list_id)
    return ListView(
        list=shopping,
        unchecked=[_item_view(session, i) for i in _unchecked_items(session, list_id)],
        checked=[_item_view(session, i) for i in _checked_items(session, list_id)],
        version=list_version(session, list_id),
    )


# --- items ---------------------------------------------------------------------

def get_item(session: Session, item_id: str) -> Item:
    """
    Return a live item.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    item = session.get(Item, item_id)
    if item is None or item.deleted_at is not None:
        raise ServiceError("error.not_found")
    return item


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
    get_list(session, list_id)
    if row_id is not None:
        repeated = session.get(Item, row_id)
        if repeated is not None:
            return AddItemResult(item=repeated, outcome="existing")
    name, quantity = _clean_item_fields(session, name, quantity, for_whom_id)
    name_key = normalise_name(name)
    matches = list(
        session.scalars(
            sync.live(
                select(Item).where(
                    Item.list_id == list_id,
                    Item.name_key == name_key,
                    Item.cleared_at.is_(None),
                )
            ).order_by(Item.created_at)
        )
    )
    for match in matches:
        if match.checked_at is None:
            return AddItemResult(item=match, outcome="existing")
    if matches:
        match = matches[0]
        match.checked_at = None
        match.checked_by_id = None
        sync.touch(match, session)
        return AddItemResult(item=match, outcome="unchecked")
    position = _next_position(
        session,
        Item.position,
        Item.list_id == list_id,
        Item.deleted_at.is_(None),
    )
    item = Item(
        id=row_id,
        list_id=list_id,
        name=name,
        name_key=name_key,
        quantity=quantity,
        for_whom_id=for_whom_id,
        added_by_id=actor_id,
        position=position,
    )
    sync.touch(item, session)
    return AddItemResult(item=item, outcome="added")


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
    item = get_item(session, item_id)
    name, quantity = _clean_item_fields(session, name, quantity, for_whom_id)
    if (item.name, item.quantity, item.for_whom_id) != (name, quantity, for_whom_id):
        item.name = name
        item.name_key = normalise_name(name)
        item.quantity = quantity
        item.for_whom_id = for_whom_id
        sync.touch(item, session)
    return item


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
    item = get_item(session, item_id)
    if item.cleared_at is not None:
        raise ServiceError("error.not_found")
    if checked and item.checked_at is None:
        item.checked_at = utc_now()
        item.checked_by_id = actor_id
        sync.touch(item, session)
    elif not checked and item.checked_at is not None:
        item.checked_at = None
        item.checked_by_id = None
        sync.touch(item, session)
    return item


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
    get_list(session, list_id)
    _apply_order(_unchecked_items(session, list_id), item_ids, session)


def clear_checked(session: Session, actor_id: str, list_id: str) -> int:
    """
    Set ``cleared_at`` on all checked, not cleared items of a list.

    Returns the number of items cleared.

    Raises
    ------
    ServiceError
        ``error.not_found`` (list).
    """
    get_list(session, list_id)
    items = _checked_items(session, list_id)
    stamp = utc_now()
    for item in items:
        item.cleared_at = stamp
        sync.touch(item, session)
    return len(items)


def restore_cleared(session: Session, actor_id: str, list_id: str) -> int:
    """
    Undo ``clear_checked``: bring back the items of the latest clearing.

    These are the live items of the list that share the most recent
    ``cleared_at``. They are checked again. Returns how many came back.

    Raises
    ------
    ServiceError
        ``error.not_found`` (list).
    """
    get_list(session, list_id)
    cleared = list(
        session.scalars(
            sync.live(
                select(Item).where(Item.list_id == list_id, Item.cleared_at.is_not(None))
            ).order_by(Item.cleared_at.desc())
        )
    )
    if not cleared:
        return 0
    latest = [item for item in cleared if item.cleared_at == cleared[0].cleared_at]
    for item in latest:
        item.cleared_at = None
        sync.touch(item, session)
    return len(latest)


def checked_items(session: Session, list_id: str) -> list[Item]:
    """
    Return the live checked, not cleared items of a list, most recently
    checked first (used by "Done shopping").

    Raises
    ------
    ServiceError
        ``error.not_found`` (list).
    """
    get_list(session, list_id)
    return _checked_items(session, list_id)


def delete_item(session: Session, actor_id: str, item_id: str) -> Item:
    """
    Soft-delete an item; returns it (for "Deleted <name> · Undo").

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    item = get_item(session, item_id)
    sync.soft_delete(item, session)
    return item


def restore_item(session: Session, actor_id: str, item_id: str) -> Item:
    """
    Undo ``delete_item``; the item keeps its old position.

    Raises
    ------
    ServiceError
        ``error.not_found`` when the item does not exist or is not deleted,
        or its list is deleted.
    """
    item = session.get(Item, item_id)
    if item is None or item.deleted_at is None:
        raise ServiceError("error.not_found")
    get_list(session, item.list_id)
    sync.restore(item, session)
    return item
