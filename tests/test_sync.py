"""Tests for services/sync.py: change counter, touch, soft delete, restore, live."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from cekar.models import ChangeCounter, Expense, ExpenseShare, Item, ShoppingList, Split
from cekar.services import sync


def make_list(session, people, items=("Milk", "Bread", "Mlik")):
    shopping = ShoppingList(name="Groceries")
    sync.touch(shopping, session)
    rows = []
    for position, name in enumerate(items):
        item = Item(
            list_id=shopping.id, name=name, name_key=name.lower(),
            added_by_id=people.ana.id, position=position,
        )
        sync.touch(item, session)
        rows.append(item)
    session.flush()
    return shopping, rows


def make_expense(session, people):
    expense = Expense(
        title="Pizza", amount_cents=2000, spent_on=people.ana.created_at.date(),
        payer_id=people.ana.id, split=Split.EQUAL, created_by_id=people.ana.id,
    )
    sync.touch(expense, session)
    shares = []
    for user in (people.ana, people.bor):
        share = ExpenseShare(expense_id=expense.id, user_id=user.id, amount_cents=1000)
        sync.touch(share, session)
        shares.append(share)
    session.flush()
    return expense, shares


def test_new_id_is_uuid4_text():
    value = sync.new_id()
    assert len(value) == 36 and uuid.UUID(value).version == 4
    assert sync.new_id() != value


def test_next_seq_strictly_increases(session):
    first = sync.next_seq(session)
    assert [sync.next_seq(session) for _ in range(3)] == [first + 1, first + 2, first + 3]
    assert session.get(ChangeCounter, 1).value == first + 3


def test_counter_starts_at_zero(session):
    assert session.get(ChangeCounter, 1).value == 0


def test_touch_adds_row_and_stamps_it(session, people):
    shopping = ShoppingList(name="Hardware store")
    sync.touch(shopping, session)
    assert len(shopping.id) == 36  # usable before any flush
    session.flush()
    assert shopping in session
    assert shopping.seq == session.get(ChangeCounter, 1).value
    before_seq, before_updated = shopping.seq, shopping.updated_at
    shopping.name = "DIY"
    sync.touch(shopping, session)
    assert shopping.seq > before_seq
    assert shopping.updated_at > before_updated


def test_changes_since_cursor(session, people):
    shopping, items = make_list(session, people)
    cursor = session.get(ChangeCounter, 1).value
    sync.touch(items[0], session)
    expense, shares = make_expense(session, people)
    changed = {
        row.id
        for model in (ShoppingList, Item, Expense, ExpenseShare)
        for row in session.scalars(select(model).where(model.seq > cursor))
    }
    assert changed == {items[0].id, expense.id, *(s.id for s in shares)}


def test_soft_delete_list_stamps_items_with_same_time(session, people):
    shopping, items = make_list(session, people)
    seq_before = shopping.seq
    stamp = sync.soft_delete(shopping, session)
    assert shopping.deleted_at == stamp and shopping.seq > seq_before
    assert all(item.deleted_at == stamp for item in items)
    # Rows stay in the database.
    assert session.scalar(select(Item).where(Item.id == items[0].id)) is items[0]


def test_soft_delete_keeps_earlier_tombstone(session, people):
    shopping, items = make_list(session, people)
    earlier = sync.soft_delete(items[2], session)
    later = sync.soft_delete(shopping, session)
    assert items[2].deleted_at == earlier != later
    assert items[0].deleted_at == later


def test_soft_delete_twice_is_an_error(session, people):
    shopping, _ = make_list(session, people)
    sync.soft_delete(shopping, session)
    with pytest.raises(ValueError, match="already deleted"):
        sync.soft_delete(shopping, session)


def test_restore_list_brings_back_only_same_deletion(session, people):
    shopping, (milk, bread, mlik) = make_list(session, people)
    mlik_deleted = sync.soft_delete(mlik, session)
    sync.soft_delete(shopping, session)
    session.flush()
    before = {row.id: (row.seq, row.updated_at) for row in (shopping, milk, bread, mlik)}

    sync.restore(shopping, session)
    session.flush()
    session.expire_all()

    assert shopping.deleted_at is None
    assert milk.deleted_at is None and bread.deleted_at is None
    assert mlik.deleted_at == mlik_deleted
    for row in (shopping, milk, bread):
        assert row.seq > before[row.id][0]
        assert row.updated_at > before[row.id][1]
    assert (mlik.seq, mlik.updated_at) == before[mlik.id]


def test_restore_expense_and_shares(session, people):
    expense, shares = make_expense(session, people)
    sync.soft_delete(expense, session)
    session.flush()
    before = {row.id: (row.seq, row.updated_at) for row in (expense, *shares)}
    sync.restore(expense, session)
    session.flush()
    for row in (expense, *shares):
        assert row.deleted_at is None
        assert row.seq > before[row.id][0]
        assert row.updated_at > before[row.id][1]


def test_restore_live_row_is_an_error(session, people):
    shopping, _ = make_list(session, people)
    with pytest.raises(ValueError, match="not deleted"):
        sync.restore(shopping, session)


def test_live_excludes_tombstones(session, people):
    shopping, (milk, bread, mlik) = make_list(session, people)
    sync.soft_delete(mlik, session)
    session.flush()
    names = session.scalars(sync.live(select(Item.name).where(Item.list_id == shopping.id)))
    assert sorted(names) == ["Bread", "Milk"]
    rows = session.scalars(sync.live(select(Item)))
    assert {row.id for row in rows} == {milk.id, bread.id}


def test_live_filters_every_selected_model(session, people):
    shopping, items = make_list(session, people)
    sync.soft_delete(shopping, session)
    session.flush()
    query = sync.live(select(Item, ShoppingList).join(ShoppingList))
    assert session.execute(query).all() == []


def test_row_without_touch_fails(session):
    session.add(ShoppingList(name="No seq"))
    with pytest.raises(Exception, match="NOT NULL"):
        session.flush()
