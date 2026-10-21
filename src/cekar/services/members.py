"""
Users, membership and per-user preferences (design D2, D3, D16).
FROZEN SIGNATURES; implemented in group 3.

Member display order (used everywhere members are listed, and by the equal
split rounding of D5) is ``member_since``, ties by ``User.id``.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from cekar.models import User, UserPreference, utc_now
from cekar.services import ServiceError, sync
from cekar.services.balances import PairBalance, pair_balances

NAME_MAX_LENGTH = 50

# Keys of ``user_preference`` rows.
LAST_LIST_ID = "last_list_id"


LAST_SEEN_REFRESH = timedelta(hours=1)


def _member_order(user: User) -> tuple:
    return (user.member_since, user.id)


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
    username = (username or "").strip() or None
    name = (display_name or "").strip() or username or ha_user_id
    now = utc_now()
    user = session.scalars(select(User).where(User.ha_user_id == ha_user_id)).first()
    if user is None:
        user = User(
            ha_user_id=ha_user_id,
            username=username,
            display_name=name,
            is_member=False,
            last_seen_at=now,
        )
        sync.touch(user, session)
        session.flush()
        return user
    changed = False
    if user.deleted_at is not None:
        user.deleted_at = None
        changed = True
    if user.username != username or user.display_name != name:
        user.username = username
        user.display_name = name
        changed = True
    if user.last_seen_at is None or now - user.last_seen_at > LAST_SEEN_REFRESH:
        user.last_seen_at = now
        changed = True
    if changed:
        sync.touch(user, session)
        session.flush()
    return user


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
    if row_id is not None:
        existing = session.get(User, row_id)
        if existing is not None:
            return existing
    name = (name or "").strip()
    if not name:
        raise ServiceError("error.person.name_required")
    if len(name) > NAME_MAX_LENGTH:
        raise ServiceError("error.person.name_too_long", max_length=NAME_MAX_LENGTH)
    taken = {u.display_name.casefold() for u in session.scalars(sync.live(select(User)))}
    if name.casefold() in taken:
        raise ServiceError("error.person.name_taken", name=name)
    user = User(display_name=name, is_member=True, member_since=utc_now())
    if row_id is not None:
        user.id = row_id
    sync.touch(user, session)
    session.flush()
    return user


def get_user(session: Session, user_id: str) -> User:
    """
    Return a live user.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise ServiceError("error.not_found")
    return user


def list_users(session: Session) -> list[User]:
    """
    Return all live users for Settings and the picker.

    Members first in display order, then non-members by display name.
    """
    users = list(session.scalars(sync.live(select(User))))
    members = sorted((u for u in users if u.is_member), key=_member_order)
    others = sorted(
        (u for u in users if not u.is_member),
        key=lambda u: (u.display_name.casefold(), u.id),
    )
    return members + others


def list_members(session: Session) -> list[User]:
    """Return live members in display order (``member_since``, then ``id``)."""
    query = sync.live(select(User)).where(User.is_member.is_(True))
    return sorted(session.scalars(query), key=_member_order)


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
    user = get_user(session, user_id)
    if user.is_member == is_member:
        return user
    user.is_member = is_member
    user.member_since = utc_now() if is_member else None
    sync.touch(user, session)
    session.flush()
    return user


def open_balances(session: Session, user_id: str) -> list[PairBalance]:
    """
    Return the non-zero pair balances that involve ``user_id`` (D16 warning).

    Uses ``balances.pair_balances``; empty when the user is settled with
    everyone.
    """
    return [
        b
        for b in pair_balances(session)
        if user_id in (b.debtor_id, b.creditor_id)
    ]


def default_payer_id(session: Session, viewer_id: str) -> str | None:
    """
    Return the default "Paid by": the viewer if a member, else the first member.

    ``None`` when there are no members.
    """
    members = list_members(session)
    if not members:
        return None
    if any(m.id == viewer_id for m in members):
        return viewer_id
    return members[0].id


def _preference(session: Session, user_id: str, key: str) -> UserPreference | None:
    query = sync.live(select(UserPreference)).where(
        UserPreference.user_id == user_id, UserPreference.key == key
    )
    return session.scalars(query).first()


def get_preference(session: Session, user_id: str, key: str) -> str | None:
    """Return a user's preference value, or ``None`` when not set."""
    preference = _preference(session, user_id, key)
    return preference.value if preference is not None else None


def set_preference(session: Session, actor_id: str, key: str, value: str | None) -> None:
    """
    Set a preference of the acting user (created on first use).

    Writes nothing when the stored value is already ``value``.
    """
    preference = _preference(session, actor_id, key)
    if preference is None:
        if value is None:
            return
        sync.touch(UserPreference(user_id=actor_id, key=key, value=value), session)
    elif preference.value != value:
        preference.value = value
        sync.touch(preference, session)
    else:
        return
    session.flush()
