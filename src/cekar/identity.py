"""
Who is acting: Ingress user headers, else the signed "Who are you?" cookie
(design D2). FROZEN SIGNATURES; implemented in group 3.

Add-on mode: ``X-Remote-User-Id`` (with ``-Name`` and ``-Display-Name``)
identifies the user and wins over any cookie; unknown ids are registered
through ``services.members.register_ha_user``. Without the headers, and
always in standalone mode, the identity cookie (signed with
``Settings.secret``, valid one year) names a user id. Without a valid
identity the web layer redirects to the picker at ``PICKER_PATH``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, Response

from cekar.models import User
from cekar.web.common import SessionDep

USER_ID_HEADER = "X-Remote-User-Id"
USER_NAME_HEADER = "X-Remote-User-Name"
DISPLAY_NAME_HEADER = "X-Remote-User-Display-Name"
IDENTITY_COOKIE = "cekar_identity"
IDENTITY_MAX_AGE = 365 * 24 * 3600
PICKER_PATH = "/who"


def resolve_user(request: Request, session: SessionDep) -> User | None:
    """
    Return the acting user, or ``None`` when the picker must be shown.

    Headers first (add-on mode only), then the identity cookie; a cookie
    that does not verify, or names an unknown or deleted user, is ignored.
    """
    raise NotImplementedError


def current_user(request: Request, session: SessionDep) -> User:
    """
    FastAPI dependency: the acting user.

    Raises
    ------
    HTTPException
        303 to ``url(request, PICKER_PATH)`` when ``resolve_user`` gives
        ``None``.
    """
    raise NotImplementedError


CurrentUser = Annotated[User, Depends(current_user)]


def set_identity_cookie(request: Request, response: Response, user_id: str) -> None:
    """Set the signed identity cookie for ``user_id`` (httponly, lax, one year)."""
    raise NotImplementedError


def clear_identity_cookie(response: Response) -> None:
    """Delete the identity cookie ("Switch person")."""
    raise NotImplementedError
