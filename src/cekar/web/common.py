"""Helpers shared by the route modules: page context, redirects, parsing."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from cekar.db import get_session
from cekar.i18n import t
from cekar.services import ServiceError, ServiceWarning
from cekar.urls import url
from cekar.web.formatting import money
from cekar.web.templating import templates

SessionDep = Annotated[Session, Depends(get_session)]

# Sent by the page script when it wants only the dialog markup of a page.
DIALOG_HEADER = "X-Cekar-Dialog"


def error_text(error: ServiceError | ServiceWarning) -> str:
    """
    Translate a service error or warning into the user's message.

    Parameters named ``*_cents`` are shown as money under the name without
    the suffix (``left_cents=500`` fills ``{left}`` with ``€5.00``).
    """
    params: dict[str, object] = {}
    for name, value in error.params.items():
        if name.endswith("_cents"):
            params[name.removesuffix("_cents")] = money(value)
        else:
            params[name] = value
    return t(error.key, **params)


def safe_next(target: str) -> str:
    """Accept only in-app paths as a redirect target (no scheme, no host)."""
    ok = target.startswith("/") and not target.startswith("//") and "\\" not in target
    return target if ok else "/"


def current_location(request: Request) -> str:
    """Path and query of this request without the Ingress prefix."""
    query = request.url.query
    return f"{request.url.path}?{query}" if query else request.url.path


def render(
    request: Request, name: str, status_code: int = 200, **context: Any
) -> HTMLResponse:
    """
    Render template ``name`` with ``context``.

    Adds ``request`` and the layout: the full page, or just the content block
    when the page script asks for a dialog.
    """
    context.setdefault("section", "lists")
    context["location"] = current_location(request)
    partial = request.headers.get(DIALOG_HEADER) == "1"
    context["layout"] = "partial.html" if partial else "base.html"
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def redirect(request: Request, path: str) -> RedirectResponse:
    """Redirect after a POST (303), keeping the Ingress prefix."""
    return RedirectResponse(url(request, path), status_code=303)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def parse_date(text: str | None, name: str) -> date | None:
    """Parse ``YYYY-MM-DD`` (blank gives ``None``); 422 for anything else."""
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise _bad_request(t("error.date.invalid")) from None


def parse_ints(values: list[str], name: str) -> tuple[int, ...]:
    """Parse repeated whole-number query values; blanks are skipped."""
    try:
        return tuple(int(v) for v in values if v != "")
    except ValueError:
        raise _bad_request(t("error.whole_numbers")) from None


async def html_error_page(request: Request, exc: StarletteHTTPException):
    """
    Exception handler: a page with a way back instead of raw JSON.

    Only client and server errors on HTML routes get the page. Redirects
    (the identity picker uses a 303), ``/api`` and ``/static`` keep the default
    JSON response.
    """
    path = request.url.path
    if exc.status_code < 400 or path.startswith(("/api", "/static")):
        return await http_exception_handler(request, exc)
    if exc.status_code == 404:
        message = t("error.not_found")
    elif exc.status_code == 422 and isinstance(exc.detail, str):
        message = exc.detail  # raised by the web layer for input the user can fix
    else:
        message = t("error.generic")
    return render(request, "error.html", exc.status_code, user=None, message=message)
