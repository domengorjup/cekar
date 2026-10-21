"""
Expenses, their shares and the expense list (design D5, D6, D11, D17).
FROZEN SIGNATURES. ``split_equal`` is implemented (group 1); the rest is
implemented in group 5.

Shares are materialised at save time (one ``ExpenseShare`` per user with a
non-zero part), so balances are plain sums:

=============  ===========================================================
``split``      Shares stored
=============  ===========================================================
``equal``      ``split_equal`` over the participants (default all members)
``exact``      one per member with a non-zero entered amount
``for_other``  one share of the full amount for ``for_user_id``
``personal``   one share of the full amount for the payer
=============  ===========================================================
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from sqlalchemy.orm import Session

from cekar.models import Expense, Split

TITLE_MAX_LENGTH = 100


@dataclass(frozen=True)
class ExpenseInput:
    """
    Fields of an expense form (create/update), in storage units.

    Which of the split fields is used depends on ``split``:

    - ``equal``: ``participant_ids``; ``None`` means all current members.
    - ``exact``: ``exact_cents`` (user id -> cents); zero amounts are dropped.
    - ``for_other``: ``for_user_id``, a member other than the payer.
    - ``personal``: none.

    Fields that do not belong to ``split`` are ignored.
    """

    title: str
    amount_cents: int
    spent_on: date
    payer_id: str
    split: Split = Split.EQUAL
    participant_ids: Sequence[str] | None = None
    exact_cents: Mapping[str, int] = field(default_factory=dict)
    for_user_id: str | None = None


@dataclass(frozen=True)
class ExpenseDetail:
    """
    A live expense for the edit form.

    ``data`` rebuilds the form input from the stored shares (participants for
    ``equal``, amounts for ``exact``, the person for ``for_other``).
    ``shares`` maps user id to cents.
    """

    expense: Expense
    data: ExpenseInput
    shares: dict[str, int]


ViewerPartKind = Literal["owe", "lent", "personal", "paid", "received", "not_involved"]


@dataclass(frozen=True)
class ViewerPart:
    """
    The viewing user's part in a row of the expense list.

    - expense paid by the viewer: ``lent`` (amount minus own share; others
      owe it), or ``personal`` for a personal expense;
    - expense with a share of the viewer, paid by someone else: ``owe``;
    - payment: ``paid`` (viewer sent it) or ``received``;
    - otherwise ``not_involved``.

    ``amount_cents`` is 0 for ``personal`` and ``not_involved``.
    """

    kind: ViewerPartKind
    amount_cents: int = 0


@dataclass(frozen=True)
class ExpenseRow:
    """An expense in the expense list."""

    id: str
    title: str
    amount_cents: int
    spent_on: date
    payer_id: str
    payer_name: str
    split: Split
    trip_id: str | None
    viewer: ViewerPart
    kind: Literal["expense"] = "expense"


@dataclass(frozen=True)
class PaymentRow:
    """A settle-up payment in the expense list."""

    id: str
    amount_cents: int
    paid_on: date
    from_user_id: str
    from_name: str
    to_user_id: str
    to_name: str
    viewer: ViewerPart
    kind: Literal["payment"] = "payment"


@dataclass(frozen=True)
class TripRow:
    """
    One shopping trip as a single collapsed row (D11).

    ``total_cents`` is the trip's receipt total. ``viewer`` sums the parts of
    its live expenses: net lent minus owed gives ``lent`` or ``owe``; zero
    gives ``personal`` when the viewer paid, else ``not_involved``.
    """

    trip_id: str
    list_name: str
    total_cents: int
    spent_on: date
    payer_id: str
    payer_name: str
    expenses: list[ExpenseRow]
    viewer: ViewerPart
    kind: Literal["trip"] = "trip"


FeedRow = ExpenseRow | PaymentRow | TripRow


@dataclass(frozen=True)
class MonthGroup:
    """Rows of one calendar month, newest first."""

    year: int
    month: int
    rows: list[FeedRow]


def split_equal(
    amount: int, participants: Sequence[str], payer: str, order: Sequence[str]
) -> dict[str, int]:
    """
    Split ``amount`` cents equally with deterministic rounding (design D5).

    Everyone gets ``amount // n``; the remaining ``amount % n`` cents go one
    each to the payer first (if participating), then to the other
    participants in ``order`` (member display order). Shares always sum to
    ``amount``. When ``amount < n`` some shares are 0; callers do not store
    zero shares.

    Parameters
    ----------
    amount : int
        Total in cents, greater than zero.
    participants : Sequence[str]
        User ids sharing the cost, without duplicates.
    payer : str
        User id of the payer (may or may not participate).
    order : Sequence[str]
        Member display order; must contain every participant.

    Returns
    -------
    dict[str, int]
        User id -> cents, in rounding order (payer first).

    Raises
    ------
    ValueError
        For a non-positive amount, no participants, duplicate participants or
        a participant missing from ``order`` (programming errors; the service
        validates user input before calling this).
    """
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    if not participants:
        raise ValueError("at least one participant is needed")
    if len(set(participants)) != len(participants):
        raise ValueError("participants contain duplicates")
    rank = {user_id: index for index, user_id in enumerate(order)}
    missing = [user_id for user_id in participants if user_id not in rank]
    if missing:
        raise ValueError(f"participants not in the member order: {missing}")
    ordered = sorted(participants, key=rank.__getitem__)
    if payer in ordered:
        ordered.remove(payer)
        ordered.insert(0, payer)
    base, remainder = divmod(amount, len(ordered))
    return {user_id: base + (1 if i < remainder else 0) for i, user_id in enumerate(ordered)}


def create_expense(
    session: Session,
    actor_id: str,
    data: ExpenseInput,
    *,
    trip_id: str | None = None,
    row_id: str | None = None,
) -> Expense:
    """
    Create an expense and its shares; ``created_by_id`` is the actor.

    ``title`` is trimmed. ``trip_id`` links the expense to a shopping trip
    (used by ``trips.complete_trip``).

    Raises
    ------
    ServiceError
        ``error.expense.fewer_than_two_members``;
        ``error.expense.title_required``; ``error.expense.title_too_long``
        (``max_length``); ``error.amount.not_positive``;
        ``error.expense.payer_not_member``;
        ``error.expense.participant_not_member`` (equal participants, exact
        users or ``for_user_id`` that are not members);
        ``error.expense.no_participants`` (equal with an empty list);
        ``error.expense.for_other_is_payer``;
        ``error.expense.share_negative``;
        ``error.expense.exact_left`` (``left_cents``) or
        ``error.expense.exact_over`` (``over_cents``) when the exact amounts
        do not sum to the total.
    """
    raise NotImplementedError


def update_expense(
    session: Session, actor_id: str, expense_id: str, data: ExpenseInput
) -> Expense:
    """
    Replace an expense's fields and shares (``trip_id`` is kept).

    Old shares are soft-deleted on their own and new ones created, so a
    later undo of a delete never brings old shares back. Same validation as
    ``create_expense``.

    Raises
    ------
    ServiceError
        ``error.not_found`` and the ``create_expense`` errors.
    """
    raise NotImplementedError


def get_expense(session: Session, expense_id: str) -> ExpenseDetail:
    """
    Return a live expense with its form input and shares.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def delete_expense(session: Session, actor_id: str, expense_id: str) -> Expense:
    """
    Soft-delete an expense and its shares (one ``deleted_at``); returns it
    (for "Deleted <title> · Undo").

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def restore_expense(session: Session, actor_id: str, expense_id: str) -> Expense:
    """
    Undo ``delete_expense``: the expense and the shares deleted with it
    come back (``sync.restore``).

    Raises
    ------
    ServiceError
        ``error.not_found`` when it does not exist or is not deleted.
    """
    raise NotImplementedError


def expense_feed(session: Session, viewer_id: str) -> list[MonthGroup]:
    """
    Return live expenses and payments, newest first, grouped by month (D11).

    Rows are ordered by date (``spent_on`` / ``paid_on``), then
    ``created_at``, both descending. Expenses with a ``trip_id`` are folded
    into one ``TripRow`` per trip, dated by the trip; a trip whose expenses
    are all deleted is left out. Each row carries the viewer's part.
    """
    raise NotImplementedError
