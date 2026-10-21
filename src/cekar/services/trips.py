"""
"Done shopping": a list's checked items and the receipt total become
expenses (design D11). FROZEN SIGNATURES; implemented in group 6 against
``services.lists`` and ``services.expenses``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from cekar.models import Expense, Item, ShoppingTrip, Split, User
from cekar.services import ServiceError, expenses, lists, members, sync


@dataclass(frozen=True)
class TripItem:
    """A checked item on the "Done shopping" form."""

    item_id: str
    name: str
    quantity: str | None
    for_whom_id: str | None
    for_whom_name: str | None


@dataclass(frozen=True)
class TripForm:
    """
    Data for the "Done shopping" form.

    ``priced``: checked items with a "for whom" (one price field each);
    ``shared``: the other checked items. ``members`` in display order for the
    paid-by dropdown; ``default_payer_id`` per ``members.default_payer_id``.
    ``enough_members`` is False with fewer than two members: the form then
    only confirms clearing (no expenses).
    """

    list_id: str
    list_name: str
    priced: list[TripItem]
    shared: list[TripItem]
    members: list[User]
    default_payer_id: str | None
    enough_members: bool


@dataclass(frozen=True)
class TripInput:
    """
    The submitted form, in storage units.

    ``prices`` maps item id to cents for the priced items that were filled
    in; blank prices are left out (the item then counts as shared).
    """

    total_cents: int
    spent_on: date
    payer_id: str
    prices: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TripResult:
    """
    What ``complete_trip`` did: the trip row (``None`` on the clear-only
    path), the created expenses and the number of items cleared.
    """

    trip: ShoppingTrip | None
    expenses: list[Expense]
    cleared: int


def _is_priceable(item: Item, member_ids: set[str]) -> bool:
    """An item can take a price when it is "for" a current member."""
    return item.for_whom_id is not None and item.for_whom_id in member_ids


def trip_form_data(session: Session, list_id: str, viewer_id: str) -> TripForm:
    """
    Return the form data for a list's checked items.

    Raises
    ------
    ServiceError
        ``error.not_found`` (list); ``error.trip.no_checked_items``.
    """
    shopping_list = lists.get_list(session, list_id)
    checked = lists.checked_items(session, list_id)
    if not checked:
        raise ServiceError("error.trip.no_checked_items")
    people = members.list_members(session)
    member_ids = {user.id for user in people}
    names = {user.id: user.display_name for user in people}
    priced: list[TripItem] = []
    shared: list[TripItem] = []
    for item in checked:
        is_priced = _is_priceable(item, member_ids)
        trip_item = TripItem(
            item_id=item.id,
            name=item.name,
            quantity=item.quantity,
            for_whom_id=item.for_whom_id if is_priced else None,
            for_whom_name=names[item.for_whom_id] if is_priced else None,
        )
        (priced if is_priced else shared).append(trip_item)
    return TripForm(
        list_id=shopping_list.id,
        list_name=shopping_list.name,
        priced=priced,
        shared=shared,
        members=people,
        default_payer_id=members.default_payer_id(session, viewer_id),
        enough_members=len(people) >= 2,
    )


def complete_trip(
    session: Session,
    actor_id: str,
    list_id: str,
    data: TripInput | None,
    *,
    row_id: str | None = None,
) -> TripResult:
    """
    Turn the checked items into expenses, then clear them (D11).

    With two or more members, in one transaction: a ``ShoppingTrip`` row,
    then, all linked to it and none with a zero amount:

    - per member other than the payer with priced items, one ``for_other``
      expense of their sum, titled ``"<list name>: <item names>"``;
    - if the payer priced items for themselves, one ``personal`` expense;
    - if ``total - sum(prices) > 0``, one ``equal`` expense among all
      members, titled with the list name;

    then all checked items of the list are cleared. Titles are cut to
    ``expenses.TITLE_MAX_LENGTH``. With fewer than two members ``data`` is
    ignored (may be ``None``): only the items are cleared and ``trip`` is
    ``None``.

    Raises
    ------
    ServiceError
        ``error.not_found`` (list); ``error.trip.no_checked_items``;
        ``error.amount.required`` (``data`` is ``None`` with two or more
        members); ``error.amount.not_positive`` (total or a price);
        ``error.expense.payer_not_member``;
        ``error.trip.item_not_priceable`` (a price for an item that is not
        checked on the list or has no "for whom");
        ``error.trip.prices_exceed_total`` (``prices_cents``,
        ``total_cents``).
    """
    if row_id is not None:
        existing = session.get(ShoppingTrip, row_id)
        if existing is not None:
            linked = list(
                session.query(Expense)
                .filter(Expense.trip_id == existing.id, Expense.deleted_at.is_(None))
                .order_by(Expense.created_at, Expense.id)
            )
            return TripResult(trip=existing, expenses=linked, cleared=0)

    shopping_list = lists.get_list(session, list_id)
    checked = lists.checked_items(session, list_id)
    if not checked:
        raise ServiceError("error.trip.no_checked_items")
    people = members.list_members(session)

    if len(people) < 2:
        return TripResult(
            trip=None, expenses=[], cleared=lists.clear_checked(session, actor_id, list_id)
        )

    # Validate everything before the first write.
    if data is None:
        raise ServiceError("error.amount.required")
    if data.total_cents <= 0:
        raise ServiceError("error.amount.not_positive")
    member_ids = {user.id for user in people}
    if data.payer_id not in member_ids:
        raise ServiceError("error.expense.payer_not_member")
    by_id = {item.id: item for item in checked}
    for item_id, cents in data.prices.items():
        item = by_id.get(item_id)
        if item is None or not _is_priceable(item, member_ids):
            raise ServiceError("error.trip.item_not_priceable")
        if cents <= 0:
            raise ServiceError("error.amount.not_positive")
    prices_cents = sum(data.prices.values())
    if prices_cents > data.total_cents:
        raise ServiceError(
            "error.trip.prices_exceed_total",
            prices_cents=prices_cents,
            total_cents=data.total_cents,
        )

    trip = ShoppingTrip(
        list_id=shopping_list.id,
        payer_id=data.payer_id,
        total_cents=data.total_cents,
        spent_on=data.spent_on,
        created_by_id=actor_id,
    )
    if row_id is not None:
        trip.id = row_id
    sync.touch(trip, session)
    session.flush()

    created: list[Expense] = []
    for user in people:  # member display order
        owned = [
            item for item in checked if item.id in data.prices and item.for_whom_id == user.id
        ]
        if not owned:
            continue
        title = f"{shopping_list.name}: {', '.join(item.name for item in owned)}"
        created.append(
            expenses.create_expense(
                session,
                actor_id,
                expenses.ExpenseInput(
                    title=title[: expenses.TITLE_MAX_LENGTH].strip(),
                    amount_cents=sum(data.prices[item.id] for item in owned),
                    spent_on=data.spent_on,
                    payer_id=data.payer_id,
                    split=Split.PERSONAL if user.id == data.payer_id else Split.FOR_OTHER,
                    for_user_id=None if user.id == data.payer_id else user.id,
                ),
                trip_id=trip.id,
            )
        )
    remainder = data.total_cents - prices_cents
    if remainder > 0:
        created.append(
            expenses.create_expense(
                session,
                actor_id,
                expenses.ExpenseInput(
                    title=shopping_list.name[: expenses.TITLE_MAX_LENGTH],
                    amount_cents=remainder,
                    spent_on=data.spent_on,
                    payer_id=data.payer_id,
                    split=Split.EQUAL,
                ),
                trip_id=trip.id,
            )
        )
    cleared = lists.clear_checked(session, actor_id, list_id)
    return TripResult(trip=trip, expenses=created, cleared=cleared)
