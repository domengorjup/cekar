"""Done shopping: the checked items and the receipt total become expenses (D11)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from cekar.identity import CurrentUser
from cekar.services import ServiceError, trips
from cekar.web.common import SessionDep, error_text, redirect, render
from cekar.web.formatting import parse_amount
from cekar.web.ui import FormData

router = APIRouter()

PRICE_PREFIX = "price_"


def _form_page(request, session, user, list_id, *, entered=None, errors=None, status=200):
    try:
        form = trips.trip_form_data(session, list_id, user.id)
    except ServiceError as exc:
        if exc.key == "error.trip.no_checked_items":
            # Someone else cleared the items meanwhile: back to the list.
            return redirect(request, f"/lists/{list_id}")
        raise HTTPException(status_code=404, detail=error_text(exc)) from exc
    entered = entered or {
        "total": "", "date": date.today().isoformat(), "payer": form.default_payer_id or "",
    }
    return render(
        request, "trip_form.html", status, user=user, form=form, f=entered,
        errors=errors or [],
    )


@router.get("/lists/{list_id}/done", response_class=HTMLResponse)
def trip_form(request: Request, session: SessionDep, user: CurrentUser, list_id: str):
    """Dialog: receipt total, date, payer and the prices of items for one person."""
    return _form_page(request, session, user, list_id)


def _parse(form, trip_form_data) -> trips.TripInput:
    """Convert the posted fields; raises ``ServiceError`` with a message key."""
    total = parse_amount(form.get("total"))
    try:
        spent_on = date.fromisoformat(form.get("date", ""))
    except ValueError:
        raise ServiceError("error.date.invalid") from None
    prices = {}
    for item in trip_form_data.priced:
        text = form.get(PRICE_PREFIX + item.item_id, "").strip()
        if text:
            prices[item.item_id] = parse_amount(text)
    return trips.TripInput(
        total_cents=total, spent_on=spent_on, payer_id=form.get("payer", ""), prices=prices
    )


@router.post("/lists/{list_id}/done")
def trip_save(request: Request, session: SessionDep, user: CurrentUser, list_id: str,
              form: FormData):
    """Record the trip and clear the checked items."""
    entered = {k: str(v) for k, v in form.items()}
    try:
        trip_form_data = trips.trip_form_data(session, list_id, user.id)
        data = _parse(form, trip_form_data) if trip_form_data.enough_members else None
        result = trips.complete_trip(session, user.id, list_id, data)
    except ServiceError as exc:
        if exc.key == "error.not_found":
            raise HTTPException(status_code=404, detail=error_text(exc)) from exc
        if exc.key == "error.trip.no_checked_items":
            return redirect(request, f"/lists/{list_id}")
        session.rollback()
        return _form_page(request, session, user, list_id, entered=entered,
                          errors=[error_text(exc)], status=422)
    if result.trip is None:
        return redirect(request, f"/lists/{list_id}?cleared={result.cleared}")
    return redirect(request, f"/expenses?trip={len(result.expenses)}")
