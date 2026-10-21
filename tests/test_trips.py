"""Tests for services/trips.py: every scenario of the shopping-trip spec."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from cekar.models import Expense, ExpenseShare, Item, ShoppingTrip, Split, User
from cekar.services import ServiceError, balances, expenses, lists, trips

DAY = date(2026, 10, 21)


class BoomError(Exception):
    """Injected failure."""


def shares_of(session: Session, expense: Expense) -> dict[str, int]:
    rows = session.scalars(
        select(ExpenseShare).where(
            ExpenseShare.expense_id == expense.id, ExpenseShare.deleted_at.is_(None)
        )
    )
    return {row.user_id: row.amount_cents for row in rows}


def add_checked(
    session: Session, actor: User, list_id: str, name: str, for_whom: User | None = None
) -> Item:
    item = lists.add_item(
        session, actor.id, list_id, name, for_whom_id=for_whom.id if for_whom else None
    ).item
    lists.set_checked(session, actor.id, item.id, True)
    return item


@pytest.fixture
def groceries(session: Session, two_people: tuple[User, User]):
    ana, _ = two_people
    shopping_list = lists.create_list(session, ana.id, "Groceries")
    session.commit()
    return shopping_list


def test_form_contents(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    milk = add_checked(session, ana, groceries.id, "Milk")
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)
    razor = add_checked(session, ana, groceries.id, "Razor", ana)
    lists.add_item(session, ana.id, groceries.id, "Bread")  # unchecked: not on the form

    form = trips.trip_form_data(session, groceries.id, ana.id)

    assert form.list_name == "Groceries"
    assert {i.item_id: i.for_whom_name for i in form.priced} == {
        shampoo.id: "Bor",
        razor.id: "Ana",
    }
    assert [i.item_id for i in form.shared] == [milk.id]
    assert [m.id for m in form.members] == [ana.id, bor.id]
    assert form.default_payer_id == ana.id
    assert form.enough_members


def test_form_without_checked_items(session: Session, two_people, groceries) -> None:
    ana, _ = two_people
    lists.add_item(session, ana.id, groceries.id, "Bread")
    with pytest.raises(ServiceError) as caught:
        trips.trip_form_data(session, groceries.id, ana.id)
    assert caught.value.key == "error.trip.no_checked_items"


def test_mixed_receipt(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    add_checked(session, ana, groceries.id, "Milk")
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)
    razor = add_checked(session, ana, groceries.id, "Razor", ana)

    result = trips.complete_trip(
        session,
        ana.id,
        groceries.id,
        trips.TripInput(
            total_cents=5000,
            spent_on=DAY,
            payer_id=ana.id,
            prices={shampoo.id: 600, razor.id: 400},
        ),
    )

    assert result.trip is not None
    assert (result.trip.total_cents, result.trip.payer_id) == (5000, ana.id)
    assert result.cleared == 3
    by_split = {e.split: e for e in result.expenses}
    assert len(result.expenses) == 3
    # For Bor: 600, titled with the list and the item names.
    for_other = by_split[Split.FOR_OTHER]
    assert for_other.amount_cents == 600
    assert for_other.title == "Groceries: Shampoo"
    assert shares_of(session, for_other) == {bor.id: 600}
    # Personal for Ana: 400.
    personal = by_split[Split.PERSONAL]
    assert personal.amount_cents == 400
    assert shares_of(session, personal) == {ana.id: 400}
    # Remainder 5000 - 600 - 400 = 4000, split 2000 / 2000.
    equal = by_split[Split.EQUAL]
    assert equal.amount_cents == 4000
    assert equal.title == "Groceries"
    assert shares_of(session, equal) == {ana.id: 2000, bor.id: 2000}
    # All linked to the trip, all paid by Ana, dated by the trip.
    assert all(e.trip_id == result.trip.id for e in result.expenses)
    assert all(e.payer_id == ana.id and e.spent_on == DAY for e in result.expenses)
    # Bor owes Ana 600 + 2000 = 2600.
    [balance] = balances.pair_balances(session)
    assert (balance.debtor_id, balance.creditor_id, balance.amount_cents) == (
        bor.id,
        ana.id,
        2600,
    )


def test_only_shared_items(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    add_checked(session, ana, groceries.id, "Milk")
    add_checked(session, ana, groceries.id, "Bread")

    result = trips.complete_trip(
        session, bor.id, groceries.id, trips.TripInput(3125, DAY, bor.id)
    )

    [expense] = result.expenses
    assert (expense.split, expense.amount_cents, expense.payer_id) == (Split.EQUAL, 3125, bor.id)
    # 3125 / 2: the odd cent goes to the payer.
    assert shares_of(session, expense) == {bor.id: 1563, ana.id: 1562}


def test_everything_priced_has_no_equal_expense(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)
    razor = add_checked(session, ana, groceries.id, "Razor", ana)

    result = trips.complete_trip(
        session,
        ana.id,
        groceries.id,
        trips.TripInput(1000, DAY, ana.id, {shampoo.id: 650, razor.id: 350}),
    )

    assert sorted((e.split, e.amount_cents) for e in result.expenses) == [
        (Split.FOR_OTHER, 650),
        (Split.PERSONAL, 350),
    ]


def test_blank_price_makes_item_shared(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)
    razor = add_checked(session, ana, groceries.id, "Razor", bor)

    result = trips.complete_trip(
        session, ana.id, groceries.id, trips.TripInput(2000, DAY, ana.id, {shampoo.id: 500})
    )

    by_split = {e.split: e for e in result.expenses}
    assert by_split[Split.FOR_OTHER].amount_cents == 500
    assert by_split[Split.FOR_OTHER].title == "Groceries: Shampoo"
    assert by_split[Split.EQUAL].amount_cents == 1500
    assert razor.cleared_at is not None  # still cleared


def test_two_items_for_same_person_make_one_expense(
    session: Session, two_people, groceries
) -> None:
    ana, bor = two_people
    a = add_checked(session, ana, groceries.id, "Soap", bor)
    b = add_checked(session, ana, groceries.id, "Towel", bor)

    result = trips.complete_trip(
        session, ana.id, groceries.id, trips.TripInput(1000, DAY, ana.id, {a.id: 300, b.id: 450})
    )

    for_other = [e for e in result.expenses if e.split == Split.FOR_OTHER]
    assert [e.amount_cents for e in for_other] == [750]
    assert for_other[0].title.startswith("Groceries: ")
    assert "Soap" in for_other[0].title and "Towel" in for_other[0].title


def test_payer_other_than_actor(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)

    result = trips.complete_trip(
        session, ana.id, groceries.id, trips.TripInput(800, DAY, bor.id, {shampoo.id: 800})
    )

    # Bor pays for an item that is for Bor: personal.
    [expense] = result.expenses
    assert (expense.split, expense.payer_id, expense.amount_cents) == (Split.PERSONAL, bor.id, 800)


def test_checked_items_cleared_unchecked_stay(session: Session, two_people, groceries) -> None:
    ana, _ = two_people
    add_checked(session, ana, groceries.id, "Milk")
    add_checked(session, ana, groceries.id, "Bread")
    for name in ("Eggs", "Rice", "Salt"):
        lists.add_item(session, ana.id, groceries.id, name)

    result = trips.complete_trip(
        session, ana.id, groceries.id, trips.TripInput(1000, DAY, ana.id)
    )

    assert result.cleared == 2
    assert lists.checked_items(session, groceries.id) == []
    live_items = session.scalars(
        select(Item).where(Item.list_id == groceries.id, Item.cleared_at.is_(None))
    ).all()
    assert sorted(i.name for i in live_items) == ["Eggs", "Rice", "Salt"]
    # Cleared items are kept (they feed suggestions).
    cleared = session.scalars(select(Item).where(Item.cleared_at.is_not(None))).all()
    assert sorted(i.name for i in cleared) == ["Bread", "Milk"]
    assert all(i.deleted_at is None for i in cleared)


def test_prices_exceed_total_rejected(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)
    razor = add_checked(session, ana, groceries.id, "Razor", ana)

    with pytest.raises(ServiceError) as caught:
        trips.complete_trip(
            session,
            ana.id,
            groceries.id,
            trips.TripInput(1000, DAY, ana.id, {shampoo.id: 700, razor.id: 500}),
        )

    assert caught.value.key == "error.trip.prices_exceed_total"
    assert caught.value.params == {"prices_cents": 1200, "total_cents": 1000}
    # Nothing was written.
    assert session.scalars(select(ShoppingTrip)).all() == []
    assert session.scalars(select(Expense)).all() == []
    assert len(lists.checked_items(session, groceries.id)) == 2


@pytest.mark.parametrize(
    ("total", "key"), [(0, "error.amount.not_positive"), (-5, "error.amount.not_positive")]
)
def test_total_must_be_positive(session: Session, two_people, groceries, total, key) -> None:
    ana, _ = two_people
    add_checked(session, ana, groceries.id, "Milk")
    with pytest.raises(ServiceError) as caught:
        trips.complete_trip(session, ana.id, groceries.id, trips.TripInput(total, DAY, ana.id))
    assert caught.value.key == key


def test_price_must_be_positive(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)
    with pytest.raises(ServiceError) as caught:
        trips.complete_trip(
            session, ana.id, groceries.id, trips.TripInput(1000, DAY, ana.id, {shampoo.id: 0})
        )
    assert caught.value.key == "error.amount.not_positive"


def test_price_for_unpriceable_item_rejected(session: Session, two_people, groceries) -> None:
    ana, bor = two_people
    milk = add_checked(session, ana, groceries.id, "Milk")  # no "for whom"
    unchecked = lists.add_item(session, ana.id, groceries.id, "Soap", for_whom_id=bor.id).item
    add_checked(session, ana, groceries.id, "Bread")
    for bad in (milk.id, unchecked.id, "not-an-item"):
        with pytest.raises(ServiceError) as caught:
            trips.complete_trip(
                session, ana.id, groceries.id, trips.TripInput(1000, DAY, ana.id, {bad: 100})
            )
        assert caught.value.key == "error.trip.item_not_priceable"


def test_payer_must_be_member(session: Session, two_people, add_user, groceries) -> None:
    ana, _ = two_people
    tablet = add_user("Tablet", member=False)
    add_checked(session, ana, groceries.id, "Milk")
    with pytest.raises(ServiceError) as caught:
        trips.complete_trip(
            session, ana.id, groceries.id, trips.TripInput(1000, DAY, tablet.id)
        )
    assert caught.value.key == "error.expense.payer_not_member"


def test_data_required_with_two_members(session: Session, two_people, groceries) -> None:
    ana, _ = two_people
    add_checked(session, ana, groceries.id, "Milk")
    with pytest.raises(ServiceError) as caught:
        trips.complete_trip(session, ana.id, groceries.id, None)
    assert caught.value.key == "error.amount.required"


def test_complete_without_checked_items(session: Session, two_people, groceries) -> None:
    ana, _ = two_people
    with pytest.raises(ServiceError) as caught:
        trips.complete_trip(session, ana.id, groceries.id, trips.TripInput(1000, DAY, ana.id))
    assert caught.value.key == "error.trip.no_checked_items"


def test_unknown_list(session: Session, two_people) -> None:
    ana, _ = two_people
    with pytest.raises(ServiceError) as caught:
        trips.complete_trip(session, ana.id, "missing", None)
    assert caught.value.key == "error.not_found"


def test_single_member_only_clears(session: Session, add_user) -> None:
    solo = add_user("Solo")
    shopping_list = lists.create_list(session, solo.id, "Solo list")
    add_checked(session, solo, shopping_list.id, "Milk")
    add_checked(session, solo, shopping_list.id, "Bread")
    lists.add_item(session, solo.id, shopping_list.id, "Eggs")

    form = trips.trip_form_data(session, shopping_list.id, solo.id)
    assert not form.enough_members

    result = trips.complete_trip(session, solo.id, shopping_list.id, None)

    assert result.trip is None
    assert result.expenses == []
    assert result.cleared == 2
    assert session.scalars(select(Expense)).all() == []
    assert session.scalars(select(ShoppingTrip)).all() == []
    assert lists.checked_items(session, shopping_list.id) == []


def test_failure_midway_rolls_back(
    session: Session, two_people, groceries, monkeypatch: pytest.MonkeyPatch
) -> None:
    ana, bor = two_people
    add_checked(session, ana, groceries.id, "Milk")
    shampoo = add_checked(session, ana, groceries.id, "Shampoo", bor)
    session.commit()

    real_create = expenses.create_expense
    calls = []

    def failing(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise BoomError("boom")
        return real_create(*args, **kwargs)

    monkeypatch.setattr(expenses, "create_expense", failing)

    with pytest.raises(BoomError):
        trips.complete_trip(
            session,
            ana.id,
            groceries.id,
            trips.TripInput(2000, DAY, ana.id, {shampoo.id: 500}),
        )
    session.rollback()  # what db.get_session does on an error

    assert len(calls) == 2
    assert session.scalars(select(ShoppingTrip)).all() == []
    assert session.scalars(select(Expense)).all() == []
    assert len(lists.checked_items(session, groceries.id)) == 2


def test_row_id_makes_repeat_harmless(session: Session, two_people, groceries) -> None:
    ana, _ = two_people
    add_checked(session, ana, groceries.id, "Milk")
    data = trips.TripInput(1000, DAY, ana.id)
    first = trips.complete_trip(session, ana.id, groceries.id, data, row_id="trip-1")
    again = trips.complete_trip(session, ana.id, groceries.id, data, row_id="trip-1")
    assert first.trip is not None and again.trip is not None
    assert again.trip.id == "trip-1"
    assert [e.id for e in again.expenses] == [e.id for e in first.expenses]
    assert len(session.scalars(select(Expense)).all()) == 1
