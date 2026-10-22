"""Shopping list pages: lists, items, the add field, suggestions, live updates."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from cekar.i18n import t
from cekar.identity import CurrentUser
from cekar.services import ServiceError, lists, members, suggestions
from cekar.web.common import SessionDep, error_text, redirect, render, safe_next
from cekar.web.ui import FormData, cleared_redirect, deleted_redirect

router = APIRouter()


def _not_found(error: ServiceError) -> HTTPException:
    return HTTPException(status_code=404, detail=error_text(error))


def _chips_context(session: SessionDep, list_id: str) -> dict:
    """Data for the list switcher chips: lists, unchecked counts, change version."""
    version = lists.lists_version(session)
    all_lists = lists.all_lists(session)
    counts = {item.id: len(lists.list_view(session, item.id).unchecked) for item in all_lists}
    return {"lists": all_lists, "counts": counts, "chips_version": version, "list_id": list_id}


def _page(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    list_id: str,
    *,
    status: int = 200,
    errors: list[str] | None = None,
    entered: dict[str, str] | None = None,
):
    """Render the list page for ``list_id`` (also remembered as last opened)."""
    try:
        lists.open_list(session, user.id, list_id)
        view = lists.list_view(session, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return render(
        request,
        "lists.html",
        status,
        user=user,
        section="lists",
        view=view,
        **_chips_context(session, list_id),
        members=members.list_members(session),
        errors=errors or [],
        entered=entered or {},
        hl=request.query_params.get("hl", ""),
        cleared=request.query_params.get("cleared", ""),
    )


@router.get("/", response_class=HTMLResponse)
def start_page(request: Request, session: SessionDep, user: CurrentUser):
    """Open the user's last list (or the first, or a new default one)."""
    start = lists.start_list(session, user.id, t("list.default_name"))
    return _page(request, session, user, start.id)


@router.get("/lists/version", response_class=PlainTextResponse)
def lists_version(session: SessionDep, user: CurrentUser):
    """Change version of all lists and items, polled for the list switcher."""
    return PlainTextResponse(str(lists.lists_version(session)))


@router.get("/lists/{list_id}/chips", response_class=HTMLResponse)
def list_chips(request: Request, session: SessionDep, user: CurrentUser, list_id: str):
    """The list switcher only (swapped in by the page script)."""
    return render(request, "list_chips.html", user=user, **_chips_context(session, list_id))


# --- list CRUD (fixed paths before /lists/{list_id}) ---------------------------


def _list_form(request, user, *, list_id=None, name="", errors=None, status=200, next_path=""):
    return render(
        request, "list_form.html", status, user=user, list_id=list_id, typed_name=name,
        errors=errors or [], next_path=next_path,
    )


@router.get("/lists/new", response_class=HTMLResponse)
def list_new(request: Request, user: CurrentUser, next: str = ""):
    """Dialog: name of a new list."""
    return _list_form(request, user, next_path=safe_next(next) if next else "")


@router.post("/lists/new")
def list_create(
    request: Request, session: SessionDep, user: CurrentUser,
    name: Annotated[str, Form()] = "", next: Annotated[str, Form()] = "",
):
    """Create a list and open it."""
    try:
        created = lists.create_list(session, user.id, name)
    except ServiceError as exc:
        session.rollback()
        return _list_form(request, user, name=name, errors=[error_text(exc)], status=422,
                          next_path=next)
    return redirect(request, safe_next(next) if next else f"/lists/{created.id}")


@router.get("/lists/{list_id}", response_class=HTMLResponse)
def list_page(request: Request, session: SessionDep, user: CurrentUser, list_id: str):
    """One list."""
    return _page(request, session, user, list_id)


@router.get("/lists/{list_id}/items", response_class=HTMLResponse)
def list_items(request: Request, session: SessionDep, user: CurrentUser, list_id: str,
               hl: str = ""):
    """The items region only (swapped in by the page script)."""
    try:
        view = lists.list_view(session, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return render(request, "list_items.html", user=user, view=view, hl=hl)


@router.get("/lists/{list_id}/version", response_class=PlainTextResponse)
def list_version(session: SessionDep, user: CurrentUser, list_id: str):
    """Change version of a list, polled by the page script (design D9)."""
    return PlainTextResponse(str(lists.list_version(session, list_id)))


@router.get("/lists/{list_id}/suggest", response_class=HTMLResponse)
def list_suggest(request: Request, session: SessionDep, user: CurrentUser, list_id: str,
                 q: str = ""):
    """Suggestions for the add field, as an HTML fragment."""
    try:
        found = suggestions.suggest(session, list_id, q)
        view = lists.list_view(session, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    checked = {lists.normalise_name(item.name) for item in view.checked}
    return render(
        request, "suggest.html", user=user, query=q,
        found=[(s, s.name_key in checked) for s in found],
    )


@router.post("/lists/{list_id}/items")
def item_add(
    request: Request, session: SessionDep, user: CurrentUser, list_id: str,
    name: Annotated[str, Form()] = "", quantity: Annotated[str, Form()] = "",
    for_whom: Annotated[str, Form()] = "",
):
    """Add an item (or highlight / uncheck the existing one, design D8)."""
    try:
        result = lists.add_item(session, user.id, list_id, name, quantity, for_whom or None)
    except ServiceError as exc:
        if exc.key == "error.not_found":
            raise _not_found(exc) from exc
        session.rollback()
        return _page(
            request, session, user, list_id, status=422, errors=[error_text(exc)],
            entered={"name": name, "quantity": quantity, "for_whom": for_whom},
        )
    return redirect(request, f"/lists/{list_id}?hl={result.item.id}")


@router.post("/lists/{list_id}/clear")
def items_clear(request: Request, session: SessionDep, user: CurrentUser, list_id: str):
    """Clear the checked items."""
    try:
        count = lists.clear_checked(session, user.id, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    if count == 0:
        return redirect(request, f"/lists/{list_id}")
    return cleared_redirect(request, f"/lists/{list_id}", list_id, count)


@router.post("/lists/{list_id}/unclear")
def items_unclear(request: Request, session: SessionDep, user: CurrentUser, list_id: str):
    """Undo "Clear checked"."""
    try:
        lists.restore_cleared(session, user.id, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return redirect(request, f"/lists/{list_id}")


@router.post("/lists/{list_id}/reorder")
def items_reorder(session: SessionDep, user: CurrentUser, list_id: str, form: FormData):
    """Save the order of the unchecked items (sent by the drag script)."""
    try:
        lists.reorder_items(session, user.id, list_id, form.getlist("ids"))
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=204)


@router.get("/lists/{list_id}/edit", response_class=HTMLResponse)
def list_edit(request: Request, session: SessionDep, user: CurrentUser, list_id: str,
              next: str = ""):
    """Dialog: rename a list; has the delete action."""
    try:
        shopping_list = lists.get_list(session, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return _list_form(request, user, list_id=list_id, name=shopping_list.name,
                      next_path=safe_next(next) if next else "")


@router.post("/lists/{list_id}/edit")
def list_update(
    request: Request, session: SessionDep, user: CurrentUser, list_id: str,
    name: Annotated[str, Form()] = "", next: Annotated[str, Form()] = "",
):
    """Rename a list."""
    try:
        lists.rename_list(session, user.id, list_id, name)
    except ServiceError as exc:
        if exc.key == "error.not_found":
            raise _not_found(exc) from exc
        session.rollback()
        return _list_form(request, user, list_id=list_id, name=name, errors=[error_text(exc)],
                          status=422, next_path=next)
    return redirect(request, safe_next(next) if next else f"/lists/{list_id}")


@router.get("/lists/{list_id}/delete", response_class=HTMLResponse)
def list_delete_confirm(request: Request, session: SessionDep, user: CurrentUser,
                        list_id: str, next: str = ""):
    """Confirm dialog: deleting a whole list is the one delete that asks."""
    try:
        view = lists.list_view(session, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    count = len(view.unchecked) + len(view.checked)
    return render(request, "list_delete.html", user=user, list=view.list, count=count,
                  next_path=safe_next(next) if next else "")


@router.post("/lists/{list_id}/delete")
def list_delete(request: Request, session: SessionDep, user: CurrentUser, list_id: str,
                next: Annotated[str, Form()] = ""):
    """Delete a list; the next page offers Undo."""
    try:
        deleted = lists.delete_list(session, user.id, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return deleted_redirect(request, safe_next(next) if next else "/", "list", deleted.id,
                            deleted.name)


@router.post("/lists/{list_id}/restore")
def list_restore(request: Request, session: SessionDep, user: CurrentUser, list_id: str):
    """Undo a list delete."""
    try:
        restored = lists.restore_list(session, user.id, list_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return redirect(request, f"/lists/{restored.id}")


@router.post("/lists/{list_id}/move")
def list_move(request: Request, session: SessionDep, user: CurrentUser, list_id: str,
              direction: Annotated[str, Form()] = "up"):
    """Move a list one place up or down (Settings), keeping the others in order."""
    ids = [item.id for item in lists.all_lists(session)]
    if list_id not in ids:
        raise HTTPException(status_code=404, detail=t("error.not_found"))
    index = ids.index(list_id)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(ids):
        ids[index], ids[target] = ids[target], ids[index]
        lists.reorder_lists(session, user.id, ids)
    return redirect(request, "/settings")


# --- items ---------------------------------------------------------------------


def _item_form(request, session, user, item, *, status=200, errors=None, entered=None):
    adder = members.get_user(session, item.added_by_id)
    return render(
        request, "item_form.html", status, user=user, item=item, adder=adder,
        members=members.list_members(session), errors=errors or [],
        f=entered or {"name": item.name, "quantity": item.quantity or "",
                      "for_whom": item.for_whom_id or ""},
    )


@router.get("/items/{item_id}/edit", response_class=HTMLResponse)
def item_edit(request: Request, session: SessionDep, user: CurrentUser, item_id: str):
    """Dialog: all fields of an item, with Delete."""
    try:
        item = lists.get_item(session, item_id)
        return _item_form(request, session, user, item)
    except ServiceError as exc:
        raise _not_found(exc) from exc


@router.post("/items/{item_id}/edit")
def item_update(
    request: Request, session: SessionDep, user: CurrentUser, item_id: str,
    name: Annotated[str, Form()] = "", quantity: Annotated[str, Form()] = "",
    for_whom: Annotated[str, Form()] = "",
):
    """Save an item's name, quantity and "for whom"."""
    try:
        item = lists.get_item(session, item_id)
        lists.update_item(session, user.id, item_id, name, quantity or None, for_whom or None)
    except ServiceError as exc:
        if exc.key == "error.not_found":
            raise _not_found(exc) from exc
        session.rollback()
        return _item_form(
            request, session, user, item, status=422, errors=[error_text(exc)],
            entered={"name": name, "quantity": quantity, "for_whom": for_whom},
        )
    return redirect(request, f"/lists/{item.list_id}")


@router.post("/items/{item_id}/check")
def item_check(request: Request, session: SessionDep, user: CurrentUser, item_id: str,
               checked: Annotated[str, Form()] = "1"):
    """Check or uncheck an item (one tap)."""
    try:
        item = lists.set_checked(session, user.id, item_id, checked == "1")
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return redirect(request, f"/lists/{item.list_id}")


@router.post("/items/{item_id}/delete")
def item_delete(request: Request, session: SessionDep, user: CurrentUser, item_id: str):
    """Delete an item without asking; the next page offers Undo."""
    try:
        item = lists.delete_item(session, user.id, item_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return deleted_redirect(request, f"/lists/{item.list_id}", "item", item.id, item.name)


@router.post("/items/{item_id}/restore")
def item_restore(request: Request, session: SessionDep, user: CurrentUser, item_id: str):
    """Undo an item delete."""
    try:
        item = lists.restore_item(session, user.id, item_id)
    except ServiceError as exc:
        raise _not_found(exc) from exc
    return redirect(request, f"/lists/{item.list_id}")
