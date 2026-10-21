"""Shared Jinja2 environment; templates build URLs only through ``url``."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from markupsafe import Markup, escape

from cekar.i18n import t, tn
from cekar.urls import url
from cekar.web import formatting

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"

templates = Jinja2Templates(directory=WEB_DIR / "templates")


@pass_context
def _icon(context: dict, name: str, size: int = 24) -> Markup:
    """Inline ``<svg>`` that references one symbol of the vendored icon sprite."""
    sprite = url(context["request"], "/static/icons.svg")
    return Markup(
        f'<svg class="mdi" width="{size}" height="{size}" aria-hidden="true">'
        f'<use href="{escape(sprite)}#{escape(name)}"/></svg>'
    )


def query_url(request: Request, **changes: str | None) -> str:
    """
    URL of the current page with query parameters replaced.

    A value of ``None`` or ``""`` removes that parameter; other parameters
    (including repeated ones) are kept, so toggles keep the active filters.
    """
    items = [(k, v) for k, v in request.query_params.multi_items() if k not in changes]
    items += [(k, v) for k, v in changes.items() if v not in (None, "")]
    query = urlencode(items)
    base = url(request, request.url.path)
    return f"{base}?{query}" if query else base


templates.env.globals["url"] = url
templates.env.globals["query_url"] = query_url
templates.env.globals["icon"] = _icon
templates.env.globals["t"] = t
templates.env.globals["tn"] = tn
templates.env.globals["money"] = formatting.money
templates.env.globals["date"] = formatting.date
templates.env.globals["month_label"] = formatting.month_label
templates.env.filters["money"] = formatting.money
templates.env.filters["cents_input"] = lambda cents: (
    "" if cents is None else formatting.format_cents(cents)
)
