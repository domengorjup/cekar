"""Expense pages: the list with balances, and the add/edit form (design D6, D11)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from cekar.identity import CurrentUser
from cekar.models import Split
from cekar.services import ServiceError, balances, expenses, members
from cekar.web.common import SessionDep, error_text, redirect, render
from cekar.web.formatting import format_cents, parse_amount
from cekar.web.ui import FormData, deleted_redirect

router = APIRouter()


def _not_found(error: ServiceError) -> HTTPException:
    return HTTPException(status_code=404, detail=error_text(error))


def _for_names(session, groups, names: dict[str, str]) -> dict[str, str]:
    """Name of the person each "for another person" row is for (row id -> name)."""
    rows = []
    for group in groups:
        for row in group.rows:
            rows.extend(row.expenses if row.kind == "trip" else [row])
    found = {}
    for row in rows:
        if row.kind == "expense" and row.split is Split.FOR_OTHER:
            for_user = expenses.get_expense(session, row.id).data.for_user_id
            found[row.id] = names.get(for_user, "")
    return found


def _live_context(session, user) -> dict:
    """Everything the balance card and the expense list show."""
    users = members.list_users(session)
    names = {u.id: u.display_name for u in users}
    groups = expenses.expense_feed(session, user.id)
    return {
        "groups": groups,
        "pairs": balances.pair_balances(session),
        "own_total": balances.user_total(session, user.id),
        "version": balances.expenses_version(session),
        "members": members.list_members(session),
        "for_names": _for_names(session, groups, names),
    }


@router.get("/expenses", response_class=HTMLResponse)
def expenses_page(request: Request, session: SessionDep, user: CurrentUser, trip: int = 0):
    """Balances, then expenses and payments newest first, grouped by month."""
    return render(
        request, "expenses.html", user=user, section="expenses", trip=trip,
        **_live_context(session, user),
    )


@router.get("/expenses/body", response_class=HTMLResponse)
def expenses_body(request: Request, session: SessionDep, user: CurrentUser):
    """The balances and list only (swapped in by the page script)."""
    return render(request, "expenses_live.html", user=user, **_live_context(session, user))


@router.get("/expenses/version", response_class=PlainTextResponse)
def expenses_version(session: SessionDep, user: CurrentUser):
    """Change version of all expenses and payments, polled by the page script."""
    return PlainTextResponse(str(balances.expenses_version(session)))


# --- add / edit form -----------------------------------------------------------


def _entered_from_detail(detail: expenses.ExpenseDetail, member_ids: list[str]) -> dict:
    data = detail.data
    return {
        "title": data.title,
        "amount": format_cents(data.amount_cents),
        "date": data.spent_on.isoformat(),
        "payer": data.payer_id,
        "split": data.split.value,
        "participants": list(data.participant_ids or member_ids),
        "for_user": data.for_user_id or "",
        "exact": {uid: format_cents(c) for uid, c in data.exact_cents.items()},
    }


def _entered_from_form(form, member_ids: list[str]) -> dict:
    return {
        "title": form.get("title", ""),
        "amount": form.get("amount", ""),
        "date": form.get("date", ""),
        "payer": form.get("payer", ""),
        "split": form.get("split", "equal"),
        "participants": form.getlist("participants"),
        "for_user": form.get("for_user", ""),
        "exact": {uid: form.get(f"exact_{uid}", "") for uid in member_ids},
    }


def _exact_cents(text: str) -> int:
    """An exact-amount field: blank or zero means no share."""
    cleaned = text.strip().replace(",", ".")
    if cleaned == "" or (cleaned.replace(".", "").isdigit() and float(cleaned) == 0):
        return 0
    return parse_amount(cleaned)


def _parse(form, member_ids: list[str]) -> expenses.ExpenseInput:
    """
    Convert the posted fields to a service input.

    Raises
    ------
    ServiceError
        For a bad amount or date (the service checks the rest).
    """
    amount = parse_amount(form.get("amount"))
    try:
        spent_on = date.fromisoformat(form.get("date", ""))
    except ValueError:
        raise ServiceError("error.date.invalid") from None
    try:
        split = Split(form.get("split", "equal"))
    except ValueError:
        raise HTTPException(status_code=422, detail="unknown split") from None
    payer = form.get("payer", "")
    for_user = form.get("for_user") or None
    if split is Split.FOR_OTHER and for_user is None:
        # Two members: "For <person>" is the one who is not the payer.
        others = [uid for uid in member_ids if uid != payer]
        for_user = others[0] if len(others) == 1 else None
    return expenses.ExpenseInput(
        title=form.get("title", ""),
        amount_cents=amount,
        spent_on=spent_on,
        payer_id=payer,
        split=split,
        participant_ids=form.getlist("participants"),
        exact_cents={uid: _exact_cents(form.get(f"exact_{uid}", "")) for uid in member_ids},
        for_user_id=for_user,
    )


def _form_page(request, session, user, *, expense_id=None, entered=None, errors=None, status=200):
    member_list = members.list_members(session)
    member_ids = [m.id for m in member_list]
    if entered is None:
        payer = members.default_payer_id(session, user.id) or ""
        entered = {
            "title": "", "amount": "", "date": date.today().isoformat(), "payer": payer,
            "split": "equal", "participants": member_ids, "for_user": "", "exact": {},
        }
    return render(
        request, "expense_form.html", status, user=user, expense_id=expense_id, f=entered,
        errors=errors or [], members=member_list,
    )


@router.get("/expenses/new", response_class=HTMLResponse)
def expense_new(request: Request, session: SessionDep, user: CurrentUser):
    """Dialog: add an expense (a hint when fewer than two people are members)."""
    return _form_page(request, session, user)


@router.post("/expenses/new")
def expense_create(request: Request, session: SessionDep, user: CurrentUser, form: FormData):
    """Create an expense."""
    member_ids = [m.id for m in members.list_members(session)]
    try:
        expenses.create_expense(session, user.id, _parse(form, member_ids))
    except ServiceError as exc:
        session.rollback()
        return _form_page(request, session, user, entered=_entered_from_form(form, member_ids),
                          errors=[error_text(exc)], status=422)
    return redirect(request, "/expenses")


@router.get("/expenses/{expense_id}/edit", response_class=HTMLResponse)
def expense_edit(request: Request, session: SessionDep, user: CurrentUser, expense_id: str):
    """Dialog: edit an expense, with Delete."""
    member_ids = [m.id for m in members.list_members(session)]
    try:
        detail = expenses.get_expense(session, expense_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return _form_page(request, session, user, expense_id=expense_id,
                      entered=_entered_from_detail(detail, member_ids))


@router.post("/expenses/{expense_id}/edit")
def expense_update(request: Request, session: SessionDep, user: CurrentUser,
                   expense_id: str, form: FormData):
    """Save an edited expense."""
    member_ids = [m.id for m in members.list_members(session)]
    try:
        expenses.update_expense(session, user.id, expense_id, _parse(form, member_ids))
    except ServiceError as exc:
        if exc.key == "error.not_found":
            raise _not_found(exc) from exc
        session.rollback()
        return _form_page(request, session, user, expense_id=expense_id,
                          entered=_entered_from_form(form, member_ids),
                          errors=[error_text(exc)], status=422)
    return redirect(request, "/expenses")


@router.post("/expenses/{expense_id}/delete")
def expense_delete(request: Request, session: SessionDep, user: CurrentUser, expense_id: str):
    """Delete an expense without asking; the next page offers Undo."""
    try:
        deleted = expenses.delete_expense(session, user.id, expense_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return deleted_redirect(request, "/expenses", "expense", deleted.id, deleted.title)


@router.post("/expenses/{expense_id}/restore")
def expense_restore(request: Request, session: SessionDep, user: CurrentUser, expense_id: str):
    """Undo an expense delete."""
    try:
        expenses.restore_expense(session, user.id, expense_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return redirect(request, "/expenses")
