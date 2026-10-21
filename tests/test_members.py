"""Tests for users, membership and preferences (household-members spec)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from cekar.models import User, UserPreference, utc_now
from cekar.services import ServiceError, members, sync


def seq(session, user) -> int:
    session.refresh(user)
    return user.seq


# --- registration ------------------------------------------------------------

def test_first_visit_creates_non_member(session):
    user = members.register_ha_user(session, "ha-1", "dana", "Dana")
    assert (user.ha_user_id, user.username, user.display_name) == ("ha-1", "dana", "Dana")
    assert user.is_member is False and user.member_since is None
    assert user.last_seen_at is not None


def test_register_same_id_returns_same_user_without_write(session):
    first = members.register_ha_user(session, "ha-1", "dana", "Dana")
    before = first.seq
    again = members.register_ha_user(session, "ha-1", "dana", "Dana")
    assert again.id == first.id and again.seq == before


def test_renamed_in_ha(session):
    user = members.register_ha_user(session, "ha-1", "dana", "Dana")
    before = user.seq
    members.register_ha_user(session, "ha-1", "dana", "Dana K.")
    assert user.display_name == "Dana K." and user.seq > before


def test_last_seen_refreshes_only_after_an_hour(session):
    user = members.register_ha_user(session, "ha-1", None, "Dana")
    user.last_seen_at = utc_now() - timedelta(minutes=30)
    old, before = user.last_seen_at, user.seq
    members.register_ha_user(session, "ha-1", None, "Dana")
    assert user.last_seen_at == old and user.seq == before
    user.last_seen_at = utc_now() - timedelta(hours=2)
    members.register_ha_user(session, "ha-1", None, "Dana")
    assert utc_now() - user.last_seen_at < timedelta(minutes=1) and user.seq > before


def test_blank_display_name_falls_back(session):
    assert members.register_ha_user(session, "ha-1", "dana", " ").display_name == "dana"
    assert members.register_ha_user(session, "ha-2", None, "").display_name == "ha-2"


# --- add person --------------------------------------------------------------

def test_add_person_is_member(session):
    ana = members.add_person(session, None, "  Ana ")
    assert ana.display_name == "Ana" and ana.is_member and ana.member_since
    assert ana.ha_user_id is None


def test_add_person_errors(session):
    members.add_person(session, None, "Ana")
    with pytest.raises(ServiceError) as e:
        members.add_person(session, None, "  ")
    assert e.value.key == "error.person.name_required"
    with pytest.raises(ServiceError) as e:
        members.add_person(session, None, "x" * 51)
    assert e.value.key == "error.person.name_too_long"
    assert e.value.params == {"max_length": members.NAME_MAX_LENGTH}
    with pytest.raises(ServiceError) as e:
        members.add_person(session, None, "ANA")
    assert e.value.key == "error.person.name_taken" and e.value.params == {"name": "ANA"}


def test_name_of_deleted_user_can_be_reused(session):
    ana = members.add_person(session, None, "Ana")
    sync.soft_delete(ana, session)
    assert members.add_person(session, None, "Ana").id != ana.id


def test_add_person_row_id_is_idempotent(session):
    first = members.add_person(session, None, "Ana", row_id="11111111-1111-1111-1111-111111111111")
    again = members.add_person(session, None, "Ana", row_id=first.id)
    assert again.id == first.id
    assert len(list(session.scalars(select(User)))) == 1


# --- lookup and order --------------------------------------------------------

def test_get_user_not_found(session, people):
    assert members.get_user(session, people.ana.id).id == people.ana.id
    with pytest.raises(ServiceError) as e:
        members.get_user(session, "nope")
    assert e.value.key == "error.not_found"
    sync.soft_delete(people.ana, session)
    with pytest.raises(ServiceError):
        members.get_user(session, people.ana.id)


def test_members_in_display_order(session, people, add_user):
    add_user("Zoe", member=False)
    assert [u.id for u in members.list_members(session)] == people.order


def test_list_users_members_first_then_by_name(session, people, add_user):
    add_user("zed", member=False)
    add_user("Adam", member=False)
    names = [u.display_name for u in members.list_users(session)]
    assert names == ["Ana", "Bor", "Cene", "Adam", "zed"]


def test_deleted_users_not_listed(session, people):
    sync.soft_delete(people.bor, session)
    assert [u.id for u in members.list_members(session)] == [people.ana.id, people.cene.id]
    assert people.bor.id not in [u.id for u in members.list_users(session)]


# --- membership --------------------------------------------------------------

def test_tick_member(session, add_user):
    tablet = add_user("Tablet", member=False)
    members.set_member(session, tablet.id, tablet.id, True)
    assert tablet.is_member and tablet.member_since
    assert tablet.id in [u.id for u in members.list_members(session)]


def test_reticking_moves_to_end(session, people):
    members.set_member(session, people.ana.id, people.ana.id, False)
    assert people.ana.member_since is None
    members.set_member(session, people.bor.id, people.ana.id, True)
    assert [u.id for u in members.list_members(session)] == [
        people.bor.id, people.cene.id, people.ana.id,
    ]


def test_set_member_no_change_writes_nothing(session, people):
    before = people.ana.seq
    members.set_member(session, people.ana.id, people.ana.id, True)
    assert people.ana.seq == before


def test_set_member_unknown(session, people):
    with pytest.raises(ServiceError) as e:
        members.set_member(session, people.ana.id, "nope", True)
    assert e.value.key == "error.not_found"


def test_turning_off_is_never_blocked_and_balance_stays(session, people):
    from cekar.services import expenses
    from cekar.services.expenses import ExpenseInput

    expenses.create_expense(
        session, people.ana.id,
        ExpenseInput(
            title="Dinner", amount_cents=2400, spent_on=utc_now().date(),
            payer_id=people.ana.id,
            participant_ids=[people.ana.id, people.bor.id],
        ),
    )
    [owed] = members.open_balances(session, people.bor.id)
    assert (owed.debtor_id, owed.creditor_id, owed.amount_cents) == (
        people.bor.id, people.ana.id, 1200,
    )
    members.set_member(session, people.ana.id, people.bor.id, False)
    assert members.open_balances(session, people.bor.id) == [owed]
    assert members.open_balances(session, people.cene.id) == []


# --- default payer -----------------------------------------------------------

def test_default_payer(session, people, add_user):
    guest = add_user("Guest", member=False)
    assert members.default_payer_id(session, people.bor.id) == people.bor.id
    assert members.default_payer_id(session, guest.id) == people.ana.id


def test_default_payer_without_members(session, add_user):
    guest = add_user("Guest", member=False)
    assert members.default_payer_id(session, guest.id) is None


# --- preferences -------------------------------------------------------------

def test_preferences(session, people):
    uid = people.ana.id
    assert members.get_preference(session, uid, members.LAST_LIST_ID) is None
    members.set_preference(session, uid, members.LAST_LIST_ID, "list-1")
    assert members.get_preference(session, uid, members.LAST_LIST_ID) == "list-1"
    assert members.get_preference(session, people.bor.id, members.LAST_LIST_ID) is None


def test_set_preference_updates_and_skips_unchanged(session, people):
    uid = people.ana.id
    members.set_preference(session, uid, members.LAST_LIST_ID, "a")
    row = session.scalars(select(UserPreference)).one()
    before = row.seq
    members.set_preference(session, uid, members.LAST_LIST_ID, "a")
    assert row.seq == before
    members.set_preference(session, uid, members.LAST_LIST_ID, "b")
    assert row.value == "b" and row.seq > before
    members.set_preference(session, uid, members.LAST_LIST_ID, None)
    assert members.get_preference(session, uid, members.LAST_LIST_ID) is None
    assert len(list(session.scalars(select(UserPreference)))) == 1
