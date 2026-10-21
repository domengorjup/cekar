"""Start page (placeholder until the lists feature exists)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from cekar.web.common import render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the empty Lists page."""
    return render(request, "lists.html", section="lists")
