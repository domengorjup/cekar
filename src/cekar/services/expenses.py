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

from sqlalchemy import select
from sqlalchemy.orm import Session

from cekar.models import Expense, ExpenseShare, Payment, ShoppingList, ShoppingTrip, Split, User
from cekar.services import ServiceError, sync

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


def _members(session: Session) -> list[User]:
    """Live members in display order."""
    query = select(User).where(User.is_member.is_(True)).order_by(User.member_since, User.id)
    return list(session.scalars(sync.live(query)))


def _compute_shares(session: Session, data: ExpenseInput) -> dict[str, int]:
    """Validate ``data`` and return the shares to store (no zero shares)."""
    members = _members(session)
    if len(members) < 2:
        raise ServiceError("error.expense.fewer_than_two_members")
    order = [member.id for member in members]
    title = data.title.strip()
    if not title:
        raise ServiceError("error.expense.title_required")
    if len(title) > TITLE_MAX_LENGTH:
        raise ServiceError("error.expense.title_too_long", max_length=TITLE_MAX_LENGTH)
    if data.amount_cents <= 0:
        raise ServiceError("error.amount.not_positive")
    if data.payer_id not in order:
        raise ServiceError("error.expense.payer_not_member")

    if data.split == Split.EQUAL:
        if data.participant_ids is None:
            participants = order
        else:
            participants = list(dict.fromkeys(data.participant_ids))
            if not participants:
                raise ServiceError("error.expense.no_participants")
            if any(user_id not in order for user_id in participants):
                raise ServiceError("error.expense.participant_not_member")
        shares = split_equal(data.amount_cents, participants, data.payer_id, order)
    elif data.split == Split.EXACT:
        if any(cents < 0 for cents in data.exact_cents.values()):
            raise ServiceError("error.expense.share_negative")
        shares = {user_id: cents for user_id, cents in data.exact_cents.items() if cents > 0}
        if any(user_id not in order for user_id in shares):
            raise ServiceError("error.expense.participant_not_member")
        difference = data.amount_cents - sum(shares.values())
        if difference > 0:
            raise ServiceError("error.expense.exact_left", left_cents=difference)
        if difference < 0:
            raise ServiceError("error.expense.exact_over", over_cents=-difference)
    elif data.split == Split.FOR_OTHER:
        if data.for_user_id not in order:
            raise ServiceError("error.expense.participant_not_member")
        if data.for_user_id == data.payer_id:
            raise ServiceError("error.expense.for_other_is_payer")
        shares = {data.for_user_id: data.amount_cents}
    else:
        shares = {data.payer_id: data.amount_cents}
    return {user_id: cents for user_id, cents in shares.items() if cents > 0}


def _add_shares(session: Session, expense: Expense, shares: dict[str, int]) -> None:
    for user_id, cents in shares.items():
        sync.touch(ExpenseShare(expense_id=expense.id, user_id=user_id, amount_cents=cents), session)


def _live_shares(session: Session, expense_id: str) -> list[ExpenseShare]:
    query = select(ExpenseShare).where(ExpenseShare.expense_id == expense_id)
    return list(session.scalars(sync.live(query.order_by(ExpenseShare.created_at))))


def _live_expense(session: Session, expense_id: str) -> Expense:
    expense = session.get(Expense, expense_id)
    if expense is None or expense.deleted_at is not None:
        raise ServiceError("error.not_found")
    return expense


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
    if row_id is not None:
        existing = session.get(Expense, row_id)
        if existing is not None:
            return existing
    shares = _compute_shares(session, data)
    expense = Expense(
        id=row_id,
        title=data.title.strip(),
        amount_cents=data.amount_cents,
        spent_on=data.spent_on,
        payer_id=data.payer_id,
        split=data.split,
        trip_id=trip_id,
        created_by_id=actor_id,
    )
    sync.touch(expense, session)
    _add_shares(session, expense, shares)
    session.flush()
    return expense


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
    expense = _live_expense(session, expense_id)
    shares = _compute_shares(session, data)
    for old in _live_shares(session, expense.id):
        sync.soft_delete(old, session)
    session.flush()
    expense.title = data.title.strip()
    expense.amount_cents = data.amount_cents
    expense.spent_on = data.spent_on
    expense.payer_id = data.payer_id
    expense.split = data.split
    sync.touch(expense, session)
    _add_shares(session, expense, shares)
    session.flush()
    return expense


def get_expense(session: Session, expense_id: str) -> ExpenseDetail:
    """
    Return a live expense with its form input and shares.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    expense = _live_expense(session, expense_id)
    shares = {share.user_id: share.amount_cents for share in _live_shares(session, expense.id)}
    data = ExpenseInput(
        title=expense.title,
        amount_cents=expense.amount_cents,
        spent_on=expense.spent_on,
        payer_id=expense.payer_id,
        split=expense.split,
        participant_ids=list(shares) if expense.split == Split.EQUAL else None,
        exact_cents=dict(shares) if expense.split == Split.EXACT else {},
        for_user_id=next(iter(shares), None) if expense.split == Split.FOR_OTHER else None,
    )
    return ExpenseDetail(expense=expense, data=data, shares=shares)


def delete_expense(session: Session, actor_id: str, expense_id: str) -> Expense:
    """
    Soft-delete an expense and its shares (one ``deleted_at``); returns it
    (for "Deleted <title> · Undo").

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    expense = _live_expense(session, expense_id)
    sync.soft_delete(expense, session)
    session.flush()
    return expense


def restore_expense(session: Session, actor_id: str, expense_id: str) -> Expense:
    """
    Undo ``delete_expense``: the expense and the shares deleted with it
    come back (``sync.restore``).

    Raises
    ------
    ServiceError
        ``error.not_found`` when it does not exist or is not deleted.
    """
    expense = session.get(Expense, expense_id)
    if expense is None or expense.deleted_at is None:
        raise ServiceError("error.not_found")
    sync.restore(expense, session)
    session.flush()
    return expense


def _viewer_part_expense(expense: Expense, shares: dict[str, int], viewer_id: str) -> ViewerPart:
    own = shares.get(viewer_id, 0)
    if expense.payer_id == viewer_id:
        lent = expense.amount_cents - own
        if expense.split == Split.PERSONAL or lent <= 0:
            return ViewerPart("personal")
        return ViewerPart("lent", lent)
    if own > 0:
        return ViewerPart("owe", own)
    return ViewerPart("not_involved")


def _trip_viewer_part(rows: list[ExpenseRow], payer_id: str, viewer_id: str) -> ViewerPart:
    net = 0
    for row in rows:
        if row.viewer.kind == "lent":
            net += row.viewer.amount_cents
        elif row.viewer.kind == "owe":
            net -= row.viewer.amount_cents
    if net > 0:
        return ViewerPart("lent", net)
    if net < 0:
        return ViewerPart("owe", -net)
    return ViewerPart("personal" if payer_id == viewer_id else "not_involved")


def expense_feed(session: Session, viewer_id: str) -> list[MonthGroup]:
    """
    Return live expenses and payments, newest first, grouped by month (D11).

    Rows are ordered by date (``spent_on`` / ``paid_on``), then
    ``created_at``, both descending. Expenses with a ``trip_id`` are folded
    into one ``TripRow`` per trip, dated by the trip; a trip whose expenses
    are all deleted is left out. Each row carries the viewer's part.
    """
    names = {user.id: user.display_name for user in session.scalars(select(User))}
    shares_by_expense: dict[str, dict[str, int]] = {}
    for share in session.scalars(sync.live(select(ExpenseShare))):
        shares_by_expense.setdefault(share.expense_id, {})[share.user_id] = share.amount_cents

    expenses = list(session.scalars(sync.live(select(Expense))))
    expenses.sort(key=lambda e: (e.spent_on, e.created_at), reverse=True)

    # (date, created_at, row) so everything can be merged and sorted once.
    entries: list[tuple[date, object, FeedRow]] = []
    trip_rows: dict[str, list[ExpenseRow]] = {}
    for expense in expenses:
        row = ExpenseRow(
            id=expense.id,
            title=expense.title,
            amount_cents=expense.amount_cents,
            spent_on=expense.spent_on,
            payer_id=expense.payer_id,
            payer_name=names[expense.payer_id],
            split=expense.split,
            trip_id=expense.trip_id,
            viewer=_viewer_part_expense(
                expense, shares_by_expense.get(expense.id, {}), viewer_id
            ),
        )
        if expense.trip_id is None:
            entries.append((expense.spent_on, expense.created_at, row))
        else:
            trip_rows.setdefault(expense.trip_id, []).append(row)

    for trip_id, rows in trip_rows.items():
        trip = session.get(ShoppingTrip, trip_id)
        shopping_list = session.get(ShoppingList, trip.list_id)
        trip_row = TripRow(
            trip_id=trip.id,
            list_name=shopping_list.name,
            total_cents=trip.total_cents,
            spent_on=trip.spent_on,
            payer_id=trip.payer_id,
            payer_name=names[trip.payer_id],
            expenses=rows,
            viewer=_trip_viewer_part(rows, trip.payer_id, viewer_id),
        )
        entries.append((trip.spent_on, trip.created_at, trip_row))

    for payment in session.scalars(sync.live(select(Payment))):
        if payment.from_user_id == viewer_id:
            viewer = ViewerPart("paid", payment.amount_cents)
        elif payment.to_user_id == viewer_id:
            viewer = ViewerPart("received", payment.amount_cents)
        else:
            viewer = ViewerPart("not_involved")
        row = PaymentRow(
            id=payment.id,
            amount_cents=payment.amount_cents,
            paid_on=payment.paid_on,
            from_user_id=payment.from_user_id,
            from_name=names[payment.from_user_id],
            to_user_id=payment.to_user_id,
            to_name=names[payment.to_user_id],
            viewer=viewer,
        )
        entries.append((payment.paid_on, payment.created_at, row))

    entries.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    groups: list[MonthGroup] = []
    for day, _, row in entries:
        if not groups or (groups[-1].year, groups[-1].month) != (day.year, day.month):
            groups.append(MonthGroup(year=day.year, month=day.month, rows=[]))
        groups[-1].rows.append(row)
    return groups
