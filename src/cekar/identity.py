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

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from cekar.auth import INGRESS_PROXY_ADDRESS
from cekar.config import Mode, Settings
from cekar.models import User
from cekar.services import members
from cekar.urls import url
from cekar.web.common import SessionDep

USER_ID_HEADER = "X-Remote-User-Id"
USER_NAME_HEADER = "X-Remote-User-Name"
DISPLAY_NAME_HEADER = "X-Remote-User-Display-Name"
IDENTITY_COOKIE = "cekar_identity"
IDENTITY_MAX_AGE = 365 * 24 * 3600
PICKER_PATH = "/who"
_SALT = "cekar-identity"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret or "", salt=_SALT)


def _header(request: Request, name: str) -> str:
    """
    Return a header value as text.

    Starlette decodes headers as Latin-1; a UTF-8 name (``Anže``) arrives as
    mojibake, so try to read the raw bytes as UTF-8 first.
    """
    value = request.headers.get(name, "")
    try:
        return value.encode("latin-1").decode("utf-8").strip()
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value.strip()


def _from_headers(request: Request, session: SessionDep) -> User | None:
    """Headers are trusted only in add-on mode from the Ingress proxy address."""
    settings: Settings = request.app.state.settings
    client = request.client.host if request.client else None
    if settings.mode is not Mode.ADDON or client != INGRESS_PROXY_ADDRESS:
        return None
    ha_user_id = _header(request, USER_ID_HEADER)
    if not ha_user_id:
        return None
    return members.register_ha_user(
        session,
        ha_user_id,
        _header(request, USER_NAME_HEADER) or None,
        _header(request, DISPLAY_NAME_HEADER),
    )


def _from_cookie(request: Request, session: SessionDep) -> User | None:
    cookie = request.cookies.get(IDENTITY_COOKIE)
    if not cookie:
        return None
    settings: Settings = request.app.state.settings
    try:
        payload = _serializer(settings).loads(cookie, max_age=IDENTITY_MAX_AGE)
    except BadSignature:
        return None
    user_id = payload.get("u") if isinstance(payload, dict) else None
    user = session.get(User, user_id) if isinstance(user_id, str) else None
    if user is None or user.deleted_at is not None:
        return None
    return user


def resolve_user(request: Request, session: SessionDep) -> User | None:
    """
    Return the acting user, or ``None`` when the picker must be shown.

    Headers first (add-on mode only), then the identity cookie; a cookie
    that does not verify, or names an unknown or deleted user, is ignored.
    """
    return _from_headers(request, session) or _from_cookie(request, session)


def current_user(request: Request, session: SessionDep) -> User:
    """
    FastAPI dependency: the acting user.

    Raises
    ------
    HTTPException
        303 to ``url(request, PICKER_PATH)`` when ``resolve_user`` gives
        ``None``.
    """
    user = resolve_user(request, session)
    if user is None:
        raise HTTPException(
            status_code=303, headers={"Location": url(request, PICKER_PATH)}
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def set_identity_cookie(request: Request, response: Response, user_id: str) -> None:
    """Set the signed identity cookie for ``user_id`` (httponly, lax, one year)."""
    settings: Settings = request.app.state.settings
    response.set_cookie(
        IDENTITY_COOKIE,
        _serializer(settings).dumps({"u": user_id}),
        max_age=IDENTITY_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_identity_cookie(response: Response) -> None:
    """Delete the identity cookie ("Switch person")."""
    response.delete_cookie(IDENTITY_COOKIE)
