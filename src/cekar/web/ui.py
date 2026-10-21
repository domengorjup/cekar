"""
Small template helpers shared by all pages: avatar colour, the delete
snackbar (design D17), "who is acting" display and match highlighting.

Registered on the Jinja environment when this module is imported.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from fastapi import Depends, Request
from fastapi.datastructures import FormData as _FormData
from fastapi.responses import RedirectResponse
from markupsafe import Markup, escape

from cekar.config import Mode
from cekar.i18n import t, tn
from cekar.identity import USER_ID_HEADER
from cekar.urls import url
from cekar.web.templating import templates

UndoKind = Literal["item", "list", "expense", "payment", "clear"]

# Undo posts to these routes (the id is a UUID).
RESTORE_PATHS: dict[str, str] = {
    "item": "/items/{id}/restore",
    "list": "/lists/{id}/restore",
    "expense": "/expenses/{id}/restore",
    "payment": "/payments/{id}/restore",
    "clear": "/lists/{id}/unclear",  # id is the list
}
_UUID = re.compile(r"^[0-9a-f-]{36}$")
_NAME_SHOWN = 60


async def read_form(request: Request) -> _FormData:
    """Dependency: the posted form with repeated and dynamic field names."""
    return await request.form()


# For forms whose field names depend on the data (prices per item, amounts per
# member) or that repeat a name (ticked members). Routes stay synchronous.
FormData = Annotated[_FormData, Depends(read_form)]


def avatar_color(user_id: str) -> int:
    """Return 1 to 5: the chart colour of a person's avatar (stable per id)."""
    return sum(ord(char) for char in user_id) % 5 + 1


def via_ha(request: Request) -> bool:
    """True when the Ingress user headers identify the person (no picker)."""
    mode = request.app.state.settings.mode
    return mode is Mode.ADDON and bool(request.headers.get(USER_ID_HEADER))


def deleted_redirect(
    request: Request, path: str, kind: UndoKind, row_id: str, name: str = ""
) -> RedirectResponse:
    """
    Redirect after a delete to ``path`` with the data for the Undo snackbar.

    The page after the redirect shows "Deleted <thing> · Undo"; without
    JavaScript that is the only way to undo.
    """
    query = f"?undo={kind}&id={row_id}"
    if name:
        query += f"&name={_quote(name)}"
    return RedirectResponse(url(request, path) + query, status_code=303)


def cleared_redirect(request: Request, path: str, list_id: str, count: int) -> RedirectResponse:
    """Redirect after "Clear checked"; the next page offers Undo (design D17)."""
    query = f"?undo=clear&id={list_id}&n={count}"
    return RedirectResponse(url(request, path) + query, status_code=303)


def _quote(text: str) -> str:
    from urllib.parse import quote

    return quote(text[:_NAME_SHOWN], safe="")


def undo_info(request: Request) -> dict | None:
    """
    Return the snackbar for this request, or ``None``.

    Reads ``?undo=<kind>&id=<uuid>&name=<text>``; anything malformed is
    ignored, so the query cannot point the Undo button anywhere else.
    """
    kind = request.query_params.get("undo", "")
    row_id = request.query_params.get("id", "")
    if kind not in RESTORE_PATHS or not _UUID.match(row_id):
        return None
    if kind == "clear":
        count = request.query_params.get("n", "")
        if not count.isdigit():
            return None
        return {"message": tn("undo.cleared", int(count)),
                "restore": RESTORE_PATHS[kind].format(id=row_id)}
    name = request.query_params.get("name", "")[:_NAME_SHOWN]
    thing = t(f"undo.thing.{kind}")
    if name:
        message = t("undo.deleted", thing=thing, name=name)
    else:
        message = t("undo.deleted_unnamed", thing=thing)
    return {"message": message, "restore": RESTORE_PATHS[kind].format(id=row_id)}


def highlight(name: str, query: str) -> Markup:
    """Return ``name`` with the typed ``query`` wrapped in ``<mark>`` (if found)."""
    query = query.strip()
    start = name.lower().find(query.lower()) if query else -1
    if start < 0:
        return escape(name)
    end = start + len(query)
    return Markup("{}<mark>{}</mark>{}").format(name[:start], name[start:end], name[end:])


templates.env.globals["avatar_color"] = avatar_color
templates.env.globals["via_ha"] = via_ha
templates.env.globals["undo_info"] = undo_info
templates.env.globals["highlight"] = highlight
