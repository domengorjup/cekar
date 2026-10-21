"""
SQLAlchemy models (design D12, D13). FROZEN INTERFACE: change only via a migration.

Every user-data table carries the sync fields of ``SyncFields``: a UUID text
primary key, ``created_at``, ``updated_at``, ``deleted_at`` (tombstone) and
``seq`` (global change number). Times are naive UTC. Money is integer cents
(EUR only). Write rows only through ``cekar.services`` (``services/sync.py``
stamps ``updated_at`` and ``seq``).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names are needed for Alembic batch operations on SQLite.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

UUID_LENGTH = 36


class Base(DeclarativeBase):
    """Declarative base for all tables."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utc_now() -> datetime:
    """Return the current time as naive UTC (the storage convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


class Split(StrEnum):
    """How an expense is shared (design D6)."""

    EQUAL = "equal"
    EXACT = "exact"
    FOR_OTHER = "for_other"
    PERSONAL = "personal"


def _enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Store enum *values* as plain strings with a CHECK constraint."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda e: [m.value for m in e],
        length=20,
    )


class SyncFields:
    """
    Sync fields shared by every user-data table (design D12).

    ``seq`` has no default on purpose: a row written without
    ``services.sync.touch`` fails with an integrity error instead of silently
    missing from "changed since N".
    """

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=_new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    seq: Mapped[int] = mapped_column(Integer, index=True)


class User(SyncFields, Base):
    """
    Everyone who has used the app, or was added by name (design D3).

    ``ha_user_id`` is set for Home Assistant users (from ``X-Remote-User-Id``)
    and ``None`` for people added in the picker or standalone Settings.
    Only members (``is_member``) can pay, owe or be "for whom". Member display
    order is ``member_since``, ties by ``id``.
    """

    __tablename__ = "user"

    ha_user_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    username: Mapped[str | None] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(100))
    is_member: Mapped[bool] = mapped_column(Boolean, default=False)
    member_since: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)


class UserPreference(SyncFields, Base):
    """One per-user value, e.g. ``last_list_id``."""

    __tablename__ = "user_preference"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    key: Mapped[str] = mapped_column(String(50))
    value: Mapped[str | None] = mapped_column(Text)


class ShoppingList(SyncFields, Base):
    """A shopping list; lists are shown by ``position``."""

    __tablename__ = "shopping_list"

    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer, default=0)


class Item(SyncFields, Base):
    """
    An item on a list (design D8).

    Unchecked: ``checked_at`` is ``None``. Checked: ``checked_at`` set and
    ``cleared_at`` ``None``. Cleared ("Clear checked" or a trip): hidden, but
    still counts for suggestions. ``name_key`` is the case-, accent- and
    space-normalised name used to group suggestions.
    """

    __tablename__ = "item"
    __table_args__ = (
        Index("ix_item_list_id_deleted_at_cleared_at", "list_id", "deleted_at", "cleared_at"),
        Index("ix_item_deleted_at_name_key", "deleted_at", "name_key"),
    )

    list_id: Mapped[str] = mapped_column(ForeignKey("shopping_list.id"))
    name: Mapped[str] = mapped_column(String(100))
    name_key: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[str | None] = mapped_column(String(30))
    for_whom_id: Mapped[str | None] = mapped_column(ForeignKey("user.id"))
    added_by_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    checked_by_id: Mapped[str | None] = mapped_column(ForeignKey("user.id"))
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime)


class ShoppingTrip(SyncFields, Base):
    """One "Done shopping" (design D11); its expenses point to it."""

    __tablename__ = "shopping_trip"

    list_id: Mapped[str] = mapped_column(ForeignKey("shopping_list.id"))
    payer_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    total_cents: Mapped[int] = mapped_column(Integer)
    spent_on: Mapped[date] = mapped_column(Date)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("user.id"))


class Expense(SyncFields, Base):
    """An expense with one payer; its shares are ``ExpenseShare`` rows (D6)."""

    __tablename__ = "expense"

    title: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int] = mapped_column(Integer)
    spent_on: Mapped[date] = mapped_column(Date)
    payer_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    split: Mapped[Split] = mapped_column(_enum(Split, "split"))
    trip_id: Mapped[str | None] = mapped_column(ForeignKey("shopping_trip.id"), index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("user.id"))


class ExpenseShare(SyncFields, Base):
    """
    The part of an expense one user carries.

    Live shares of an expense sum to its amount and are unique per user
    (partial unique index over live rows).
    """

    __tablename__ = "expense_share"
    __table_args__ = (
        Index(
            "uq_expense_share_live",
            "expense_id",
            "user_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    expense_id: Mapped[str] = mapped_column(ForeignKey("expense.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)


class Payment(SyncFields, Base):
    """A settle-up payment from one user to another (design D7)."""

    __tablename__ = "payment"

    from_user_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    to_user_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    paid_on: Mapped[date] = mapped_column(Date)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("user.id"))


class ChangeCounter(Base):
    """The single global change number (row ``id == 1``); never deleted."""

    __tablename__ = "change_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class Setting(Base):
    """App-wide key/value (e.g. the generated cookie-signing secret). Not synced."""

    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
