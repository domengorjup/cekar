"""Settle up: payments between two members, edit, delete, undo (design D7)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from cekar.identity import CurrentUser
from cekar.services import ServiceError, balances, members
from cekar.web.common import SessionDep, error_text, redirect, render
from cekar.web.formatting import format_cents, parse_amount
from cekar.web.ui import deleted_redirect

router = APIRouter()


def _not_found(error: ServiceError) -> HTTPException:
    return HTTPException(status_code=404, detail=error_text(error))


def _owed(session, from_id: str, to_id: str) -> int:
    """What ``from_id`` currently owes ``to_id`` (0 when nothing)."""
    for pair in balances.pair_balances(session):
        if pair.debtor_id == from_id and pair.creditor_id == to_id:
            return pair.amount_cents
    return 0


def _form_page(request, session, user, *, f, payment_id=None, errors=None, warnings=None,
               status=200):
    try:
        from_user = members.get_user(session, f["from"])
        to_user = members.get_user(session, f["to"])
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return render(
        request, "payment_form.html", status, user=user, f=f, payment_id=payment_id,
        from_user=from_user, to_user=to_user, owed=_owed(session, f["from"], f["to"]),
        errors=errors or [], warnings=warnings or [],
    )


@router.get("/settle", response_class=HTMLResponse)
def settle_form(request: Request, session: SessionDep, user: CurrentUser,
                debtor: str = "", creditor: str = ""):
    """Dialog: pay back a pair's net, prefilled and editable (partial is fine)."""
    owed = _owed(session, debtor, creditor)
    f = {
        "from": debtor, "to": creditor, "amount": format_cents(owed) if owed else "",
        "date": date.today().isoformat(), "confirmed": "",
    }
    return _form_page(request, session, user, f=f)


def _save(request, session, user, f, payment_id=None):
    """Check, warn about an over-payment once, then save."""
    try:
        try:
            paid_on = date.fromisoformat(f["date"])
        except ValueError:
            raise ServiceError("error.date.invalid") from None
        data = balances.PaymentInput(f["from"], f["to"], parse_amount(f["amount"]), paid_on)
        warnings = [] if f["confirmed"] else balances.check_payment(
            session, data, payment_id=payment_id)
        if warnings:
            f = {**f, "confirmed": "1"}
            return _form_page(request, session, user, f=f, payment_id=payment_id,
                              warnings=[error_text(w) for w in warnings])
        if payment_id is None:
            balances.create_payment(session, user.id, data)
        else:
            balances.update_payment(session, user.id, payment_id, data)
    except ServiceError as exc:
        if exc.key == "error.not_found":
            raise _not_found(exc) from exc
        session.rollback()
        return _form_page(request, session, user, f=f, payment_id=payment_id,
                          errors=[error_text(exc)], status=422)
    return redirect(request, "/expenses")


@router.post("/settle")
def settle_save(
    request: Request, session: SessionDep, user: CurrentUser,
    debtor: Annotated[str, Form()] = "", creditor: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "", paid_on: Annotated[str, Form(alias="date")] = "",
    confirmed: Annotated[str, Form()] = "",
):
    """Record a payment."""
    f = {"from": debtor, "to": creditor, "amount": amount, "date": paid_on,
         "confirmed": confirmed}
    return _save(request, session, user, f)


@router.get("/payments/{payment_id}/edit", response_class=HTMLResponse)
def payment_edit(request: Request, session: SessionDep, user: CurrentUser, payment_id: str):
    """Dialog: edit a payment, with Delete."""
    try:
        payment = balances.get_payment(session, payment_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    f = {
        "from": payment.from_user_id, "to": payment.to_user_id,
        "amount": format_cents(payment.amount_cents), "date": payment.paid_on.isoformat(),
        "confirmed": "",
    }
    return _form_page(request, session, user, f=f, payment_id=payment_id)


@router.post("/payments/{payment_id}/edit")
def payment_update(
    request: Request, session: SessionDep, user: CurrentUser, payment_id: str,
    debtor: Annotated[str, Form()] = "", creditor: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "", paid_on: Annotated[str, Form(alias="date")] = "",
    confirmed: Annotated[str, Form()] = "",
):
    """Save an edited payment."""
    f = {"from": debtor, "to": creditor, "amount": amount, "date": paid_on,
         "confirmed": confirmed}
    return _save(request, session, user, f, payment_id)


@router.post("/payments/{payment_id}/delete")
def payment_delete(request: Request, session: SessionDep, user: CurrentUser, payment_id: str):
    """Delete a payment without asking; the next page offers Undo."""
    try:
        deleted = balances.delete_payment(session, user.id, payment_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return deleted_redirect(request, "/expenses", "payment", deleted.id)


@router.post("/payments/{payment_id}/restore")
def payment_restore(request: Request, session: SessionDep, user: CurrentUser, payment_id: str):
    """Undo a payment delete."""
    try:
        balances.restore_payment(session, user.id, payment_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return redirect(request, "/expenses")
