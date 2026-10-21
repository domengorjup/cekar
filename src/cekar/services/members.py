"""
Users, membership and per-user preferences (design D2, D3, D16).
FROZEN SIGNATURES; implemented in group 3.

Member display order (used everywhere members are listed, and by the equal
split rounding of D5) is ``member_since``, ties by ``User.id``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from cekar.models import User
from cekar.services.balances import PairBalance

NAME_MAX_LENGTH = 50

# Keys of ``user_preference`` rows.
LAST_LIST_ID = "last_list_id"


def register_ha_user(
    session: Session, ha_user_id: str, username: str | None, display_name: str
) -> User:
    """
    Return the user for a Home Assistant user id, creating it on first visit.

    A new user is not a member. A known user's ``username`` and
    ``display_name`` are updated when the header values changed. ``last_seen_at``
    is set on create and refreshed when it is more than an hour old, so a
    page view does not write (and take a ``seq``) on every request. A blank
    display name falls back to the username, then to the HA user id.
    The acting user is the user itself.
    """
    raise NotImplementedError


def add_person(
    session: Session, actor_id: str | None, name: str, *, row_id: str | None = None
) -> User:
    """
    Add a person by name (picker or standalone Settings); they start as a member.

    ``actor_id`` is ``None`` when nobody is identified yet (the "Who are you?"
    page). ``name`` is trimmed.

    Raises
    ------
    ServiceError
        ``error.person.name_required``; ``error.person.name_too_long``
        (``max_length``); ``error.person.name_taken`` (``name``) when a live
        user already has that display name (case-insensitive).
    """
    raise NotImplementedError


def get_user(session: Session, user_id: str) -> User:
    """
    Return a live user.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def list_users(session: Session) -> list[User]:
    """
    Return all live users for Settings and the picker.

    Members first in display order, then non-members by display name.
    """
    raise NotImplementedError


def list_members(session: Session) -> list[User]:
    """Return live members in display order (``member_since``, then ``id``)."""
    raise NotImplementedError


def set_member(session: Session, actor_id: str, user_id: str, is_member: bool) -> User:
    """
    Turn "Member of shared expenses" on or off for a user.

    Turning it on sets ``member_since`` to now (also when re-ticked, so the
    person moves to the end of the display order). Turning it off clears
    ``member_since`` and is never blocked (D16); the web layer shows
    ``open_balances`` as a warning first. A call that changes nothing writes
    nothing.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def open_balances(session: Session, user_id: str) -> list[PairBalance]:
    """
    Return the non-zero pair balances that involve ``user_id`` (D16 warning).

    Uses ``balances.pair_balances``; empty when the user is settled with
    everyone.
    """
    raise NotImplementedError


def default_payer_id(session: Session, viewer_id: str) -> str | None:
    """
    Return the default "Paid by": the viewer if a member, else the first member.

    ``None`` when there are no members.
    """
    raise NotImplementedError


def get_preference(session: Session, user_id: str, key: str) -> str | None:
    """Return a user's preference value, or ``None`` when not set."""
    raise NotImplementedError


def set_preference(session: Session, actor_id: str, key: str, value: str | None) -> None:
    """
    Set a preference of the acting user (created on first use).

    Writes nothing when the stored value is already ``value``.
    """
    raise NotImplementedError
