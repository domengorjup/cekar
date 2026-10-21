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

from sqlalchemy.orm import Session

from cekar.models import Payment
from cekar.services import ServiceWarning


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


def pair_balances(session: Session) -> list[PairBalance]:
    """
    Return every pair with a non-zero net, once each.

    Sorted by debtor display name, then creditor display name.
    """
    raise NotImplementedError


def user_total(session: Session, user_id: str) -> int:
    """
    Return the user's net over all pairs, in cents.

    Positive: others owe the user in total; negative: the user owes; 0: all
    settled.
    """
    raise NotImplementedError


def expenses_version(session: Session) -> int:
    """
    Return the largest ``seq`` over expenses, shares and payments, tombstones
    included (polled by the expenses page, D9). 0 when there are none.
    """
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


def get_payment(session: Session, payment_id: str) -> Payment:
    """
    Return a live payment.

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def delete_payment(session: Session, actor_id: str, payment_id: str) -> Payment:
    """
    Soft-delete a payment; returns it (for "Deleted payment · Undo").

    Raises
    ------
    ServiceError
        ``error.not_found``.
    """
    raise NotImplementedError


def restore_payment(session: Session, actor_id: str, payment_id: str) -> Payment:
    """
    Undo ``delete_payment``.

    Raises
    ------
    ServiceError
        ``error.not_found`` when it does not exist or is not deleted.
    """
    raise NotImplementedError
