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

from cekar.models import Expense, ShoppingTrip, User


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


def trip_form_data(session: Session, list_id: str, viewer_id: str) -> TripForm:
    """
    Return the form data for a list's checked items.

    Raises
    ------
    ServiceError
        ``error.not_found`` (list); ``error.trip.no_checked_items``.
    """
    raise NotImplementedError


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
    raise NotImplementedError
