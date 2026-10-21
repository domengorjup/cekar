"""Expense service tests (shares, validation, delete/restore, feed)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from cekar.models import Expense, ExpenseShare, ShoppingList, ShoppingTrip, Split
from cekar.services import ServiceError, expenses as ex, sync
from cekar.services.balances import PaymentInput, create_payment

DAY = date(2026, 3, 10)


def inp(payer, amount, split=Split.EQUAL, title="Pizza", spent_on=DAY, **kw):
    return ex.ExpenseInput(
        title=title, amount_cents=amount, spent_on=spent_on, payer_id=payer.id, split=split, **kw
    )


def shares(session, expense):
    return dict(ex.get_expense(session, expense.id).shares)


def test_equal_two_members_odd_cent(session, two_people):
    ana, bor = two_people
    e = ex.create_expense(session, ana.id, inp(ana, 1001))
    assert shares(session, e) == {ana.id: 501, bor.id: 500}
    assert e.created_by_id == ana.id


def test_equal_three_members(session, people):
    e = ex.create_expense(session, people.ana.id, inp(people.ana, 1000))
    assert shares(session, e) == {people.ana.id: 334, people.bor.id: 333, people.cene.id: 333}


def test_equal_payer_not_participating(session, people):
    e = ex.create_expense(
        session,
        people.ana.id,
        inp(people.ana, 1001, participant_ids=[people.cene.id, people.bor.id]),
    )
    assert shares(session, e) == {people.bor.id: 501, people.cene.id: 500}


def test_equal_amount_smaller_than_participants_drops_zero_shares(session, people):
    e = ex.create_expense(session, people.bor.id, inp(people.bor, 2))
    assert shares(session, e) == {people.bor.id: 1, people.ana.id: 1}


def test_exact(session, people):
    e = ex.create_expense(
        session,
        people.ana.id,
        inp(
            people.ana,
            3000,
            Split.EXACT,
            exact_cents={people.ana.id: 1000, people.bor.id: 2000, people.cene.id: 0},
        ),
    )
    detail = ex.get_expense(session, e.id)
    assert detail.shares == {people.ana.id: 1000, people.bor.id: 2000}
    assert detail.data.exact_cents == detail.shares


def test_exact_left_and_over(session, people):
    ana, bor = people.ana, people.bor
    with pytest.raises(ServiceError) as err:
        ex.create_expense(
            session, ana.id, inp(ana, 3000, Split.EXACT, exact_cents={ana.id: 1000, bor.id: 1500})
        )
    assert (err.value.key, err.value.params) == ("error.expense.exact_left", {"left_cents": 500})
    with pytest.raises(ServiceError) as err:
        ex.create_expense(
            session, ana.id, inp(ana, 3000, Split.EXACT, exact_cents={ana.id: 2000, bor.id: 1500})
        )
    assert (err.value.key, err.value.params) == ("error.expense.exact_over", {"over_cents": 500})
    with pytest.raises(ServiceError) as err:
        ex.create_expense(
            session, ana.id, inp(ana, 3000, Split.EXACT, exact_cents={ana.id: 4000, bor.id: -1000})
        )
    assert err.value.key == "error.expense.share_negative"


def test_for_other(session, two_people):
    ana, bor = two_people
    e = ex.create_expense(session, ana.id, inp(ana, 2490, Split.FOR_OTHER, for_user_id=bor.id))
    detail = ex.get_expense(session, e.id)
    assert detail.shares == {bor.id: 2490}
    assert detail.data.for_user_id == bor.id


def test_for_other_is_payer_or_non_member(session, two_people, add_user):
    ana, _ = two_people
    guest = add_user("Dana", member=False)
    with pytest.raises(ServiceError) as err:
        ex.create_expense(session, ana.id, inp(ana, 100, Split.FOR_OTHER, for_user_id=ana.id))
    assert err.value.key == "error.expense.for_other_is_payer"
    with pytest.raises(ServiceError) as err:
        ex.create_expense(session, ana.id, inp(ana, 100, Split.FOR_OTHER, for_user_id=guest.id))
    assert err.value.key == "error.expense.participant_not_member"


def test_personal(session, two_people):
    ana, _ = two_people
    e = ex.create_expense(session, ana.id, inp(ana, 800, Split.PERSONAL))
    assert shares(session, e) == {ana.id: 800}


@pytest.mark.parametrize(
    ("change", "key"),
    [
        ({"title": "  "}, "error.expense.title_required"),
        ({"title": "x" * 101}, "error.expense.title_too_long"),
        ({"amount_cents": 0}, "error.amount.not_positive"),
        ({"amount_cents": -5}, "error.amount.not_positive"),
        ({"participant_ids": []}, "error.expense.no_participants"),
        ({"participant_ids": ["nobody"]}, "error.expense.participant_not_member"),
    ],
)
def test_validation(session, two_people, change, key):
    ana, _ = two_people
    values = {"title": "Pizza", "amount_cents": 500, "participant_ids": None} | change
    data = ex.ExpenseInput(
        title=values["title"],
        amount_cents=values["amount_cents"],
        spent_on=DAY,
        payer_id=ana.id,
        participant_ids=values["participant_ids"],
    )
    with pytest.raises(ServiceError) as err:
        ex.create_expense(session, ana.id, data)
    assert err.value.key == key
    assert session.scalars(select(Expense)).first() is None


def test_payer_must_be_member_and_two_members_needed(session, add_user):
    ana = add_user("Ana")
    with pytest.raises(ServiceError) as err:
        ex.create_expense(session, ana.id, inp(ana, 100))
    assert err.value.key == "error.expense.fewer_than_two_members"
    add_user("Bor")
    guest = add_user("Dana", member=False)
    with pytest.raises(ServiceError) as err:
        ex.create_expense(session, ana.id, inp(guest, 100))
    assert err.value.key == "error.expense.payer_not_member"


def test_title_trimmed_and_row_id_idempotent(session, two_people):
    ana, _ = two_people
    first = ex.create_expense(session, ana.id, inp(ana, 100, title="  Milk "), row_id="x-1")
    again = ex.create_expense(session, ana.id, inp(ana, 999, title="Other"), row_id="x-1")
    assert first is again
    assert first.title == "Milk"
    assert first.amount_cents == 100


def test_update_replaces_shares_and_delete_restore(session, people):
    ana, bor, cene = people.ana, people.bor, people.cene
    e = ex.create_expense(session, ana.id, inp(ana, 1000))
    ex.update_expense(
        session, ana.id, e.id, inp(ana, 900, Split.FOR_OTHER, title="Beer", for_user_id=cene.id)
    )
    assert shares(session, e) == {cene.id: 900}
    all_shares = list(session.scalars(select(ExpenseShare)))
    assert len(all_shares) == 4  # 3 old (tombstoned) + 1 new
    ex.delete_expense(session, bor.id, e.id)
    with pytest.raises(ServiceError):
        ex.get_expense(session, e.id)
    with pytest.raises(ServiceError):
        ex.delete_expense(session, bor.id, e.id)
    ex.restore_expense(session, bor.id, e.id)
    assert shares(session, e) == {cene.id: 900}  # old shares stay deleted
    with pytest.raises(ServiceError):
        ex.restore_expense(session, bor.id, e.id)
    with pytest.raises(ServiceError):
        ex.update_expense(session, ana.id, "missing", inp(ana, 100))


def test_get_equal_rebuilds_participants(session, people):
    e = ex.create_expense(
        session,
        people.ana.id,
        inp(people.ana, 1000, participant_ids=[people.ana.id, people.cene.id]),
    )
    data = ex.get_expense(session, e.id).data
    assert set(data.participant_ids) == {people.ana.id, people.cene.id}


def test_feed_viewer_parts_and_months(session, people):
    ana, bor, cene = people.ana, people.bor, people.cene
    ex.create_expense(session, ana.id, inp(ana, 1000, title="Pizza"))
    ex.create_expense(session, bor.id, inp(bor, 600, Split.PERSONAL, title="Book"))
    ex.create_expense(
        session, ana.id, inp(ana, 500, spent_on=date(2026, 2, 1), title="Old"),
    )
    create_payment(session, bor.id, PaymentInput(bor.id, ana.id, 200, date(2026, 3, 11)))

    groups = ex.expense_feed(session, ana.id)
    assert [(g.year, g.month) for g in groups] == [(2026, 3), (2026, 2)]
    march = groups[0].rows
    assert [r.kind for r in march] == ["payment", "expense", "expense"]
    assert march[0].viewer == ex.ViewerPart("received", 200)
    by_title = {r.title: r for r in march if r.kind == "expense"}
    assert by_title["Pizza"].viewer == ex.ViewerPart("lent", 666)
    assert by_title["Book"].viewer == ex.ViewerPart("not_involved")

    bor_view = ex.expense_feed(session, bor.id)[0].rows
    pizza = next(r for r in bor_view if r.kind == "expense" and r.title == "Pizza")
    book = next(r for r in bor_view if r.kind == "expense" and r.title == "Book")
    assert pizza.viewer == ex.ViewerPart("owe", 333)
    assert book.viewer == ex.ViewerPart("personal")
    assert bor_view[0].viewer == ex.ViewerPart("paid", 200)
    assert ex.expense_feed(session, cene.id)[0].rows[0].viewer.kind == "not_involved"


def test_feed_orders_same_day_by_creation_and_skips_deleted(session, two_people):
    ana, _ = two_people
    first = ex.create_expense(session, ana.id, inp(ana, 100, title="First"))
    ex.create_expense(session, ana.id, inp(ana, 100, title="Second"))
    gone = ex.create_expense(session, ana.id, inp(ana, 100, title="Gone"))
    ex.delete_expense(session, ana.id, gone.id)
    titles = [r.title for r in ex.expense_feed(session, ana.id)[0].rows]
    assert titles == ["Second", "First"]



def _trip(session, ana, titles_amounts):
    shopping_list = ShoppingList(name="Groceries")
    sync.touch(shopping_list, session)
    trip = ShoppingTrip(
        list_id=shopping_list.id, payer_id=ana.id, total_cents=5000, spent_on=DAY,
        created_by_id=ana.id,
    )
    sync.touch(trip, session)
    session.flush()
    return trip, [
        ex.create_expense(session, ana.id, inp(ana, cents, title=title), trip_id=trip.id)
        for title, cents in titles_amounts
    ]


def test_feed_folds_trip_into_one_row(session, two_people):
    ana, bor = two_people
    trip, created = _trip(session, ana, [("Milk", 1000), ("Bread", 2000), ("Soap", 2000)])
    rows = ex.expense_feed(session, bor.id)[0].rows
    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "trip"
    assert (row.list_name, row.total_cents, row.payer_name) == ("Groceries", 5000, "Ana")
    assert len(row.expenses) == 3
    assert row.viewer == ex.ViewerPart("owe", 2500)
    assert ex.expense_feed(session, ana.id)[0].rows[0].viewer == ex.ViewerPart("lent", 2500)
    # Only live expenses count; an all-deleted trip disappears.
    ex.delete_expense(session, ana.id, created[0].id)
    assert len(ex.expense_feed(session, bor.id)[0].rows[0].expenses) == 2
    for e in created[1:]:
        ex.delete_expense(session, ana.id, e.id)
    assert ex.expense_feed(session, bor.id) == []


def test_trip_of_personal_expenses_is_personal_for_payer(session, two_people):
    ana, bor = two_people
    shopping_list = ShoppingList(name="Home")
    sync.touch(shopping_list, session)
    trip = ShoppingTrip(
        list_id=shopping_list.id, payer_id=ana.id, total_cents=300, spent_on=DAY,
        created_by_id=ana.id,
    )
    sync.touch(trip, session)
    session.flush()
    ex.create_expense(session, ana.id, inp(ana, 300, Split.PERSONAL), trip_id=trip.id)
    assert ex.expense_feed(session, ana.id)[0].rows[0].viewer == ex.ViewerPart("personal")
    assert ex.expense_feed(session, bor.id)[0].rows[0].viewer == ex.ViewerPart("not_involved")
