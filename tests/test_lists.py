"""Tests for services/lists.py (shopping-lists and sync-readiness specs)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from cekar.models import Item, ShoppingList
from cekar.services import ServiceError, lists, sync


def names(views):
    return [v.name for v in views]


@pytest.fixture
def groceries(session, people):
    shopping = lists.create_list(session, people.ana.id, "Groceries")
    session.flush()
    return shopping


def add(session, people, shopping, name, **kw):
    return lists.add_item(session, people.ana.id, shopping.id, name, **kw).item


def test_normalise_name():
    assert lists.normalise_name("  Čaj  Zeleni") == "caj zeleni"
    assert lists.normalise_name("MILK") == "milk"


def test_two_lists_in_creation_order(session, people):
    lists.create_list(session, people.ana.id, "Groceries")
    lists.create_list(session, people.ana.id, "  Hardware store ")
    assert [s.name for s in lists.all_lists(session)] == ["Groceries", "Hardware store"]


def test_list_name_errors(session, people):
    with pytest.raises(ServiceError) as err:
        lists.create_list(session, people.ana.id, "   ")
    assert err.value.key == "error.list.name_required"
    with pytest.raises(ServiceError) as err:
        lists.create_list(session, people.ana.id, "x" * 51)
    assert err.value.key == "error.list.name_too_long"
    assert err.value.params == {"max_length": 50}


def test_rename_and_not_found(session, people, groceries):
    assert lists.rename_list(session, people.ana.id, groceries.id, " Food ").name == "Food"
    with pytest.raises(ServiceError) as err:
        lists.rename_list(session, people.ana.id, "nope", "Food")
    assert err.value.key == "error.not_found"


def test_create_list_with_same_row_id_is_idempotent(session, people):
    first = lists.create_list(session, people.ana.id, "Groceries", row_id="a" * 36)
    second = lists.create_list(session, people.ana.id, "Groceries", row_id="a" * 36)
    session.flush()
    assert first is second
    assert len(lists.all_lists(session)) == 1


def test_start_list_creates_default_then_reuses(session, people):
    first = lists.start_list(session, people.ana.id, "Shopping")
    assert first.name == "Shopping"
    assert lists.start_list(session, people.ana.id, "Shopping").id == first.id
    assert len(lists.all_lists(session)) == 1


def test_last_opened_list(session, people, groceries):
    hardware = lists.create_list(session, people.ana.id, "Hardware store")
    lists.open_list(session, people.ana.id, hardware.id)
    assert lists.start_list(session, people.ana.id, "Shopping").id == hardware.id
    assert lists.start_list(session, people.bor.id, "Shopping").id == groceries.id


def test_open_writes_preference_only_on_change(session, people, groceries):
    lists.open_list(session, people.ana.id, groceries.id)
    session.flush()
    before = sync.next_seq(session)
    lists.open_list(session, people.ana.id, groceries.id)
    session.flush()
    assert sync.next_seq(session) == before + 1


def test_start_list_skips_deleted_last_list(session, people, groceries):
    hardware = lists.create_list(session, people.ana.id, "Hardware store")
    lists.open_list(session, people.ana.id, hardware.id)
    lists.delete_list(session, people.ana.id, hardware.id)
    assert lists.start_list(session, people.ana.id, "Shopping").id == groceries.id


def test_reorder_lists(session, people):
    a = lists.create_list(session, people.ana.id, "A")
    b = lists.create_list(session, people.ana.id, "B")
    c = lists.create_list(session, people.ana.id, "C")
    lists.reorder_lists(session, people.ana.id, [c.id, "unknown"])
    assert [s.name for s in lists.all_lists(session)] == ["C", "A", "B"]
    seq = b.seq
    lists.reorder_lists(session, people.ana.id, [c.id, a.id, b.id])
    assert b.seq == seq


def test_add_item_with_quantity(session, people, groceries):
    add(session, people, groceries, "Bread")
    milk = add(session, people, groceries, " Milk ", quantity=" 2 l ")
    view = lists.list_view(session, groceries.id)
    assert names(view.unchecked) == ["Bread", "Milk"]
    assert view.unchecked[1].quantity == "2 l"
    assert view.unchecked[1].added_by_name == "Ana"
    assert milk.added_by_id == people.ana.id


def test_blank_quantity_is_none(session, people, groceries):
    assert add(session, people, groceries, "Milk", quantity="  ").quantity is None


def test_item_for_a_person(session, people, groceries):
    add(session, people, groceries, "Shampoo", for_whom_id=people.ana.id)
    view = lists.list_view(session, groceries.id)
    assert view.unchecked[0].for_whom_name == "Ana"


def test_item_validation(session, people, add_user, groceries):
    guest = add_user("Guest", member=False)
    cases = [
        (dict(name="   "), "error.item.name_required"),
        (dict(name="x" * 101), "error.item.name_too_long"),
        (dict(name="Milk", quantity="q" * 31), "error.item.quantity_too_long"),
        (dict(name="Milk", for_whom_id=guest.id), "error.item.for_whom_not_member"),
    ]
    for kw, key in cases:
        with pytest.raises(ServiceError) as err:
            lists.add_item(session, people.ana.id, groceries.id, **kw)
        assert err.value.key == key
    with pytest.raises(ServiceError) as err:
        lists.add_item(session, people.ana.id, "nope", "Milk")
    assert err.value.key == "error.not_found"
    assert lists.list_view(session, groceries.id).unchecked == []


def test_add_same_row_id_twice_gives_one_item(session, people, groceries):
    row_id = "b" * 36
    lists.add_item(session, people.ana.id, groceries.id, "Milk", row_id=row_id)
    again = lists.add_item(session, people.ana.id, groceries.id, "Milk", row_id=row_id)
    session.flush()
    assert again.outcome == "existing"
    assert len(session.scalars(select(Item)).all()) == 1


def test_readd_unchecked_is_existing(session, people, groceries):
    milk = add(session, people, groceries, "Milk")
    result = lists.add_item(session, people.bor.id, groceries.id, "  MILK ", "2 l")
    assert result.outcome == "existing"
    assert result.item.id == milk.id
    assert milk.quantity is None
    assert len(lists.list_view(session, groceries.id).unchecked) == 1


def test_readd_checked_unchecks_it(session, people, groceries):
    bread = add(session, people, groceries, "Bread")
    add(session, people, groceries, "Eggs")
    lists.set_checked(session, people.ana.id, bread.id, True)
    result = lists.add_item(session, people.ana.id, groceries.id, "bread")
    assert result.outcome == "unchecked"
    view = lists.list_view(session, groceries.id)
    assert names(view.unchecked) == ["Bread", "Eggs"]
    assert view.checked == []


def test_readd_cleared_adds_new(session, people, groceries):
    bread = add(session, people, groceries, "Bread")
    lists.set_checked(session, people.ana.id, bread.id, True)
    lists.clear_checked(session, people.ana.id, groceries.id)
    result = lists.add_item(session, people.ana.id, groceries.id, "Bread")
    assert result.outcome == "added"
    assert result.item.id != bread.id


def test_check_uncheck_keeps_position(session, people, groceries):
    milk = add(session, people, groceries, "Milk")
    add(session, people, groceries, "Bread")
    lists.set_checked(session, people.bor.id, milk.id, True)
    view = lists.list_view(session, groceries.id)
    assert names(view.checked) == ["Milk"]
    assert names(view.unchecked) == ["Bread"]
    assert milk.checked_by_id == people.bor.id
    lists.set_checked(session, people.bor.id, milk.id, False)
    assert names(lists.list_view(session, groceries.id).unchecked) == ["Milk", "Bread"]


def test_checked_newest_first(session, people, groceries):
    a = add(session, people, groceries, "A")
    b = add(session, people, groceries, "B")
    lists.set_checked(session, people.ana.id, a.id, True)
    lists.set_checked(session, people.ana.id, b.id, True)
    assert names(lists.list_view(session, groceries.id).checked) == ["B", "A"]
    assert [i.name for i in lists.checked_items(session, groceries.id)] == ["B", "A"]


def test_set_checked_no_change_writes_nothing(session, people, groceries):
    milk = add(session, people, groceries, "Milk")
    session.flush()
    seq = milk.seq
    lists.set_checked(session, people.ana.id, milk.id, False)
    assert milk.seq == seq


def test_set_checked_on_cleared_item_not_found(session, people, groceries):
    milk = add(session, people, groceries, "Milk")
    lists.set_checked(session, people.ana.id, milk.id, True)
    lists.clear_checked(session, people.ana.id, groceries.id)
    with pytest.raises(ServiceError) as err:
        lists.set_checked(session, people.ana.id, milk.id, False)
    assert err.value.key == "error.not_found"


def test_clear_checked(session, people, groceries):
    for name in ("A", "B", "C"):
        item = add(session, people, groceries, name)
        lists.set_checked(session, people.ana.id, item.id, True)
    add(session, people, groceries, "D")
    assert lists.clear_checked(session, people.ana.id, groceries.id) == 3
    view = lists.list_view(session, groceries.id)
    assert view.checked == []
    assert names(view.unchecked) == ["D"]
    assert lists.clear_checked(session, people.ana.id, groceries.id) == 0


def test_update_item(session, people, groceries):
    milk = add(session, people, groceries, "Milk")
    lists.update_item(session, people.ana.id, milk.id, " Oat milk ", "1 l", people.bor.id)
    assert (milk.name, milk.name_key, milk.quantity, milk.for_whom_id) == (
        "Oat milk", "oat milk", "1 l", people.bor.id,
    )
    with pytest.raises(ServiceError) as err:
        lists.update_item(session, people.ana.id, milk.id, "", None, None)
    assert err.value.key == "error.item.name_required"


def test_reorder_items(session, people, groceries):
    a, b, c = (add(session, people, groceries, n) for n in "ABC")
    lists.reorder_items(session, people.ana.id, groceries.id, [c.id, "unknown", b.id])
    assert names(lists.list_view(session, groceries.id).unchecked) == ["C", "B", "A"]
    with pytest.raises(ServiceError):
        lists.reorder_items(session, people.ana.id, "nope", [])


def test_undo_item_delete_keeps_position(session, people, groceries):
    add(session, people, groceries, "Bread")
    milk = add(session, people, groceries, "Milk")
    add(session, people, groceries, "Eggs")
    lists.delete_item(session, people.ana.id, milk.id)
    assert names(lists.list_view(session, groceries.id).unchecked) == ["Bread", "Eggs"]
    with pytest.raises(ServiceError):
        lists.get_item(session, milk.id)
    lists.restore_item(session, people.ana.id, milk.id)
    assert names(lists.list_view(session, groceries.id).unchecked) == ["Bread", "Milk", "Eggs"]


def test_restore_item_errors(session, people, groceries):
    milk = add(session, people, groceries, "Milk")
    with pytest.raises(ServiceError):
        lists.restore_item(session, people.ana.id, milk.id)
    lists.delete_item(session, people.ana.id, milk.id)
    lists.delete_list(session, people.ana.id, groceries.id)
    with pytest.raises(ServiceError):
        lists.restore_item(session, people.ana.id, milk.id)


def test_undo_list_delete(session, people, groceries):
    add(session, people, groceries, "Milk")
    lists.delete_list(session, people.ana.id, groceries.id)
    assert lists.all_lists(session) == []
    with pytest.raises(ServiceError):
        lists.list_view(session, groceries.id)
    lists.restore_list(session, people.ana.id, groceries.id)
    assert names(lists.list_view(session, groceries.id).unchecked) == ["Milk"]
    with pytest.raises(ServiceError):
        lists.restore_list(session, people.ana.id, groceries.id)


def test_undo_list_keeps_earlier_deleted_item_deleted(session, people, groceries):
    add(session, people, groceries, "Bread")
    mlik = add(session, people, groceries, "Mlik")
    lists.delete_item(session, people.ana.id, mlik.id)
    lists.delete_list(session, people.ana.id, groceries.id)
    lists.restore_list(session, people.ana.id, groceries.id)
    assert names(lists.list_view(session, groceries.id).unchecked) == ["Bread"]
    assert mlik.deleted_at is not None


def test_list_version_changes_on_every_write(session, people, groceries):
    other = lists.create_list(session, people.ana.id, "Other")
    session.flush()
    seen = [lists.list_version(session, groceries.id)]
    milk = add(session, people, groceries, "Milk")
    seen.append(lists.list_version(session, groceries.id))
    lists.set_checked(session, people.ana.id, milk.id, True)
    seen.append(lists.list_version(session, groceries.id))
    lists.delete_item(session, people.ana.id, milk.id)
    seen.append(lists.list_version(session, groceries.id))
    assert seen == sorted(set(seen))
    before = lists.list_version(session, groceries.id)
    add(session, people, other, "Nails")
    assert lists.list_version(session, groceries.id) == before
    assert lists.list_version(session, "unknown") == 0


def test_writes_stamp_seq_and_updated_at(session, people, groceries):
    milk = add(session, people, groceries, "Milk")
    session.flush()
    seq, updated = milk.seq, milk.updated_at
    lists.set_checked(session, people.ana.id, milk.id, True)
    assert milk.seq > seq
    assert milk.updated_at >= updated


def test_deleted_list_items_stay_in_database(session, people, groceries):
    add(session, people, groceries, "Milk")
    lists.delete_list(session, people.ana.id, groceries.id)
    session.flush()
    rows = session.scalars(select(Item)).all()
    assert len(rows) == 1 and rows[0].deleted_at is not None
    assert session.get(ShoppingList, groceries.id).deleted_at == rows[0].deleted_at
