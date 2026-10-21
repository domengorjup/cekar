"""
Pair balances and settle-up payments (design D7, D16, D17).
FROZEN SIGNATURES; implemented in group 5.

For each live expense with payer P and each live share (M, a) with M != P,
M owes P the amount a. A live payment from X to Y of x reduces what X owes
Y by x. Nets are per unordered pair; there is no debt simplification.
Balances include former members until settled (D16).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cekar.models import Expense, ExpenseShare, Payment, User
from cekar.services import ServiceError, ServiceWarning, sync


@dataclass(frozen=True)
class PairBalance:
    """``debtor`` owes ``creditor`` ``amount_cents`` (always > 0)."""

    debtor_id: str
    debtor_name: str
    creditor_id: str
    creditor_name: str
    amount_cents: int


@dataclass(frozen=True)
class PaymentInput:
    """Fields of a payment form (create/update)."""

    from_user_id: str
    to_user_id: str
    amount_cents: int
    paid_on: date


def _owed(session: Session, exclude_payment_id: str | None = None) -> dict[tuple[str, str], int]:
    """Net per ordered pair: ``(debtor, creditor)`` -> cents, positive only."""
    gross: dict[tuple[str, str], int] = {}
    shares = (
        select(Expense.payer_id, ExpenseShare.user_id, ExpenseShare.amount_cents)
        .join(Expense, Expense.id == ExpenseShare.expense_id)
        .where(Expense.deleted_at.is_(None), ExpenseShare.deleted_at.is_(None))
    )
    for payer_id, user_id, cents in session.execute(shares):
        if user_id != payer_id:
            gross[(user_id, payer_id)] = gross.get((user_id, payer_id), 0) + cents
    for payment in session.scalars(sync.live(select(Payment))):
        if payment.id != exclude_payment_id:
            key = (payment.from_user_id, payment.to_user_id)
            gross[key] = gross.get(key, 0) - payment.amount_cents
    net: dict[tuple[str, str], int] = {}
    for debtor, creditor in {tuple(sorted(pair)) for pair in gross}:
        difference = gross.get((debtor, creditor), 0) - gross.get((creditor, debtor), 0)
        if difference > 0:
            net[(debtor, creditor)] = difference
        elif difference < 0:
            net[(creditor, debtor)] = -difference
    return net


def pair_balances(session: Session) -> list[PairBalance]:
    """
    Return every pair with a non-zero net, once each.

    Sorted by debtor display name, then creditor display name.
    """
    names = {user.id: user.display_name for user in session.scalars(select(User))}
    balances = [
        PairBalance(debtor, names[debtor], creditor, names[creditor], cents)
        for (debtor, creditor), cents in _owed(session).items()
    ]
    return sorted(balances, key=lambda b: (b.debtor_name, b.creditor_name))


def user_total(session: Session, user_id: str) -> int:
    """
    Return the user's net over all pairs, in cents.

    Positive: others owe the user in total; negative: the user owes; 0: all
    settled.
    """
    total = 0
    for (debtor, creditor), cents in _owed(session).items():
        if creditor == user_id:
            total += cents
        elif debtor == user_id:
            total -= cents
    return total


def expenses_version(session: Session) -> int:
    """
    Return the largest ``seq`` over expenses, shares and payments, tombstones
    included (polled by the expenses page, D9). 0 when there are none.
    """
    return max(
        session.scalar(select(func.coalesce(func.max(model.seq), 0)))
        for model in (Expense, ExpenseShare, Payment)
    )


def check_payment(
    session: Session, data: PaymentInput, *, payment_id: str | None = None
) -> list[ServiceWarning]:
    """
    Return warnings to confirm before saving a payment; does not write.

    ``warning.payment.overpay`` (``owed_cents``, ``excess_cents``) when the
    amount is more than ``from_user_id`` currently owes ``to_user_id``
    (``owed_cents`` may be 0). When editing, pass ``payment_id`` so the
    payment's own current amount is left out of what is owed.
    """
    owed = _owed(session, payment_id).get((data.from_user_id, data.to_user_id), 0)
    if data.amount_cents > owed:
        return [
            ServiceWarning(
                "warning.payment.overpay",
                {"owed_cents": owed, "excess_cents": data.amount_cents - owed},
            )
        ]
    return []


def _validate_payment(
    session: Session, data: PaymentInput, payment_id: str | None = None
) -> None:
    if data.amount_cents <= 0:
        raise ServiceError("error.amount.not_positive")
    if data.from_user_id == data.to_user_id:
        raise ServiceError("error.payment.same_person")
    users = []
    for user_id in (data.from_user_id, data.to_user_id):
        user = session.get(User, user_id)
        if user is None or user.deleted_at is not None:
            raise ServiceError("error.not_found")
        users.append(user)
    if not all(user.is_member for user in users):
        nets = _owed(session, payment_id)
        pair = (data.from_user_id, data.to_user_id)
        if not (nets.get(pair) or nets.get(pair[::-1])):
            raise ServiceError("error.payment.not_member")


def _live_payment(session: Session, payment_id: str) -> Payment:
    payment = session.get(Payment, payment_id)
    if payment is None or payment.deleted_at is not None:
        raise ServiceError("error.not_found")
    return payment


def create_payment(
    session: Session, actor_id: str, data: PaymentInput, *, row_id: str | None = None
) -> Payment:
    """
    Record a payment; ``created_by_id`` is the actor. Over-payment is allowed
    (the web layer shows ``check_payment`` warnings first).

    Raises
    ------
    ServiceError
        ``error.amount.not_positive``; ``error.payment.same_person``;
        ``error.not_found`` (unknown user); ``error.payment.not_member``
        when a side is not a member and the pair has no open balance
        (settling up with a former member stays possible, D16).
    """
    if row_id is not None:
        existing = session.get(Payment, row_id)
        if existing is not None:
            return existing
    _validate_payment(session, data)
    payment = Payment(
        id=row_id,
        from_user_id=data.from_user_id,
        to_user_id=data.to_user_id,
        amount_cents=data.amount_cents,
        paid_on=data.paid_on,
        created_by_id=actor_id,
    )
    sync.touch(payment, session)
    session.flush()
    return payment


def update_payment(
    session: Session, actor_id: str, payment_id: str, data: PaymentInput
) -> Payment:
    """
    Edit a payment. Same validation as ``create_payment``.

    Raises
    ------
    ServiceError
        ``error.not_found`` and the ``create_payment`` errors.
    """
    payment = _live_payment(session, payment_id)
    _validate_payment(session, data, payment_id)
    payment.from_user_id = data.from_user_id
    payment.to_user_id = data.to_user_id
    payment.amount_cents = data.amount_cents
    payment.paid_on = data.paid_on
    sync.touch(payment, session)
    session.flush()
    return payment


def get_payment(session: Session, payment_id: str) -> Payment:
    """
    Return a live payment.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    return _live_payment(session, payment_id)


def delete_payment(session: Session, actor_id: str, payment_id: str) -> Payment:
    """
    Soft-delete a payment; returns it (for "Deleted payment · Undo").

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    payment = _live_payment(session, payment_id)
    sync.soft_delete(payment, session)
    session.flush()
    return payment


def restore_payment(session: Session, actor_id: str, payment_id: str) -> Payment:
    """
    Undo ``delete_payment``.

    Raises
    ------
    ServiceError
        ``error.not_found`` when it does not exist or is not deleted.
    """
    payment = session.get(Payment, payment_id)
    if payment is None or payment.deleted_at is None:
        raise ServiceError("error.not_found")
    sync.restore(payment, session)
    session.flush()
    return payment
