"""
Sync-readiness helpers (design D12, D17). FROZEN INTERFACE.

Every service write stamps the row with ``touch``: ``updated_at`` and the next
value of the global change counter in ``seq``. Deletes are tombstones
(``soft_delete``); a parent and the children it cascades to share one
``deleted_at`` value, so ``restore`` brings back exactly that deletion.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from cekar.models import (
    ChangeCounter,
    Expense,
    ExpenseShare,
    Item,
    ShoppingList,
    SyncFields,
    utc_now,
)

# Parent model -> (child model, name of the child's foreign key to the parent).
CASCADES: dict[type[SyncFields], list[tuple[type[SyncFields], str]]] = {
    ShoppingList: [(Item, "list_id")],
    Expense: [(ExpenseShare, "expense_id")],
}


def new_id() -> str:
    """Return a new UUID4 primary key as 36-character text."""
    return str(uuid.uuid4())


def next_seq(session: Session) -> int:
    """
    Take the next value of the global change counter.

    Runs in the session's transaction, so the value is only used if the
    transaction commits; values are strictly increasing.
    """
    statement = (
        update(ChangeCounter.__table__)
        .where(ChangeCounter.id == 1)
        .values(value=ChangeCounter.value + 1)
        .returning(ChangeCounter.value)
    )
    return session.execute(statement).scalar_one()


def touch(row: SyncFields, session: Session) -> None:
    """
    Stamp a written row: ``updated_at`` now and a new ``seq``.

    A new row gets its UUID here (the column default only applies at
    INSERT), so its ``id`` can be used for children before any flush. The
    row is added to the session. Call it on every create and update of a
    user-data row.
    """
    # Take the number before adding: ``next_seq`` autoflushes, and a new row
    # must not be inserted without its ``seq``.
    seq = next_seq(session)
    if row.id is None:
        row.id = new_id()
    row.updated_at = utc_now()
    row.seq = seq
    session.add(row)


def _children(
    row: SyncFields, session: Session, deleted_at: datetime | None
) -> list[SyncFields]:
    """Return the cascade children of ``row`` whose ``deleted_at`` matches."""
    children: list[SyncFields] = []
    for model, foreign_key in CASCADES.get(type(row), []):
        query = select(model).where(getattr(model, foreign_key) == row.id)
        if deleted_at is None:
            query = query.where(model.deleted_at.is_(None))
        else:
            query = query.where(model.deleted_at == deleted_at)
        children.extend(session.scalars(query))
    return children


def soft_delete(row: SyncFields, session: Session) -> datetime:
    """
    Tombstone ``row`` and its live cascade children with one ``deleted_at``.

    Children already deleted earlier keep their own ``deleted_at``. Every
    changed row is touched.

    Returns
    -------
    datetime
        The shared ``deleted_at`` value.

    Raises
    ------
    ValueError
        If ``row`` is already deleted (services check this first and raise
        ``ServiceError("error.not_found")``).
    """
    if row.deleted_at is not None:
        raise ValueError(f"{type(row).__name__} {row.id} is already deleted")
    stamp = utc_now()
    for child in _children(row, session, None):
        child.deleted_at = stamp
        touch(child, session)
    row.deleted_at = stamp
    touch(row, session)
    return stamp


def restore(row: SyncFields, session: Session) -> None:
    """
    Undo a ``soft_delete``: clear ``deleted_at`` on ``row`` and on the
    children deleted together with it (same ``deleted_at``).

    Children deleted earlier stay deleted. Every changed row is touched, so
    it gets a newer ``updated_at`` and ``seq``.

    Raises
    ------
    ValueError
        If ``row`` is not deleted.
    """
    if row.deleted_at is None:
        raise ValueError(f"{type(row).__name__} {row.id} is not deleted")
    for child in _children(row, session, row.deleted_at):
        child.deleted_at = None
        touch(child, session)
    row.deleted_at = None
    touch(row, session)


def live(query: Select) -> Select:
    """
    Add ``deleted_at IS NULL`` for every sync model selected by ``query``.

    Example: ``session.scalars(live(select(Item).where(Item.list_id == x)))``.
    Models reached only through a join are not filtered; add their condition
    by hand.
    """
    seen: set[type] = set()
    for description in query.column_descriptions:
        entity = description.get("entity")
        if isinstance(entity, type) and issubclass(entity, SyncFields) and entity not in seen:
            seen.add(entity)
            query = query.where(entity.deleted_at.is_(None))
    return query
