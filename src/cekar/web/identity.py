"""The "Who are you?" picker and "Switch person" (design D2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from cekar.identity import clear_identity_cookie, resolve_user, set_identity_cookie
from cekar.services import ServiceError, members
from cekar.web.common import SessionDep, error_text, redirect, render
from cekar.web.ui import via_ha

router = APIRouter()


def _page(request, session, *, errors=None, name="", status=200):
    return render(
        request, "who.html", status, user=resolve_user(request, session), section="",
        people=members.list_users(session), errors=errors or [], typed_name=name,
    )


@router.get("/who", response_class=HTMLResponse)
def who_page(request: Request, session: SessionDep):
    """List the known people; with Ingress headers there is nothing to pick."""
    if via_ha(request):
        return redirect(request, "/")
    return _page(request, session)


@router.post("/who")
def who_pick(request: Request, session: SessionDep, user_id: Annotated[str, Form()] = ""):
    """Remember the chosen person on this device (signed cookie, one year)."""
    try:
        person = members.get_user(session, user_id)
    except ServiceError as exc:
        raise HTTPException(status_code=404, detail=error_text(exc)) from exc
    response = redirect(request, "/")
    set_identity_cookie(request, response, person.id)
    return response


@router.post("/who/add")
def who_add(request: Request, session: SessionDep, name: Annotated[str, Form()] = ""):
    """Add a person by name (they start as a member) and continue as them."""
    current = resolve_user(request, session)
    try:
        person = members.add_person(session, current.id if current else None, name)
    except ServiceError as exc:
        session.rollback()
        return _page(request, session, errors=[error_text(exc)], name=name, status=422)
    response = redirect(request, "/")
    set_identity_cookie(request, response, person.id)
    return response


@router.post("/who/switch")
def who_switch(request: Request):
    """Forget the chosen person and show the picker."""
    response = redirect(request, "/who")
    clear_identity_cookie(response)
    return response
