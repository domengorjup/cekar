"""Settings: members of shared expenses, people, lists (design D3, D16)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from cekar.config import Mode
from cekar.identity import CurrentUser
from cekar.services import ServiceError, lists, members
from cekar.web.common import SessionDep, error_text, redirect, render
from cekar.web.ui import via_ha

router = APIRouter()


def _can_add_person(request: Request) -> bool:
    """People are added by hand in standalone mode and in the picker fallback."""
    return request.app.state.settings.mode is Mode.STANDALONE or not via_ha(request)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: SessionDep, user: CurrentUser):
    """Members, people and lists."""
    all_lists = lists.all_lists(session)
    counts = {
        item.id: len(lists.list_view(session, item.id).unchecked) for item in all_lists
    }
    return render(
        request, "settings.html", user=user, section="settings",
        people=members.list_users(session), lists=all_lists, counts=counts,
        can_add_person=_can_add_person(request), can_switch=not via_ha(request),
    )


@router.post("/settings/members/{user_id}")
def member_set(
    request: Request, session: SessionDep, user: CurrentUser, user_id: str,
    member: Annotated[str, Form()] = "", confirmed: Annotated[str, Form()] = "",
):
    """
    Turn "Member of shared expenses" on or off.

    Turning a member off with an open balance first shows a warning with the
    amount (design D16); it is never blocked.
    """
    try:
        person = members.get_user(session, user_id)
        is_member = member == "1"
        open_balances = []
        if person.is_member and not is_member and not confirmed:
            open_balances = members.open_balances(session, user_id)
        if open_balances:
            return render(
                request, "member_off.html", user=user, section="settings", person=person,
                balances=open_balances,
            )
        members.set_member(session, user.id, user_id, is_member)
    except ServiceError as exc:
        raise HTTPException(status_code=404, detail=error_text(exc)) from exc
    return redirect(request, "/settings")


@router.get("/settings/people/new", response_class=HTMLResponse)
def person_new(request: Request, user: CurrentUser):
    """Dialog: add a person by name."""
    if not _can_add_person(request):
        raise HTTPException(status_code=404)
    return render(request, "person_form.html", user=user, typed_name="", errors=[],
                  section="settings", name_max=members.NAME_MAX_LENGTH)


@router.post("/settings/people/new")
def person_create(request: Request, session: SessionDep, user: CurrentUser,
                  name: Annotated[str, Form()] = ""):
    """Add the person; they start as a member."""
    if not _can_add_person(request):
        raise HTTPException(status_code=404)
    try:
        members.add_person(session, user.id, name)
    except ServiceError as exc:
        session.rollback()
        return render(request, "person_form.html", 422, user=user, typed_name=name,
                      errors=[error_text(exc)], section="settings",
                      name_max=members.NAME_MAX_LENGTH)
    return redirect(request, "/settings")
