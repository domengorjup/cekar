"""Tests for identity (headers, picker cookie) and the session-key fix."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from cekar.app import create_app
from cekar.auth import INGRESS_PROXY_ADDRESS, SESSION_COOKIE
from cekar.config import Mode, Settings
from cekar.identity import (
    DISPLAY_NAME_HEADER,
    IDENTITY_COOKIE,
    PICKER_PATH,
    USER_ID_HEADER,
    USER_NAME_HEADER,
    CurrentUser,
    clear_identity_cookie,
    set_identity_cookie,
)
from cekar.models import User
from cekar.services import sync
from fastapi import Request, Response


PROTECTED = "/api/v1/health"  # needs a login session when a password is set


def build(engine, tmp_path: Path, *, host: str, **kw) -> TestClient:
    """Client for an app with test routes ``/whoami``, ``/pick/{id}``, ``/clear``."""
    app = create_app(Settings(data_dir=tmp_path, **kw), engine)

    @app.get("/whoami")
    def whoami(user: CurrentUser) -> dict:
        return {"id": user.id, "name": user.display_name}

    @app.get("/pick/{user_id}")
    def pick(request: Request, user_id: str) -> Response:
        response = Response()
        set_identity_cookie(request, response, user_id)
        return response

    @app.get("/clear")
    def clear() -> Response:
        response = Response()
        clear_identity_cookie(response)
        return response

    return TestClient(app, client=(host, 50000), follow_redirects=False)


def headers(ha_id: str, name: str = "ana", display: str = "Ana") -> dict[str, str]:
    return {
        USER_ID_HEADER: ha_id,
        USER_NAME_HEADER: name,
        DISPLAY_NAME_HEADER: display,
    }


def addon(engine, tmp_path, host=INGRESS_PROXY_ADDRESS, **kw) -> TestClient:
    return build(engine, tmp_path, host=host, mode=Mode.ADDON, **kw)


def users(session) -> list[User]:
    session.expire_all()
    return list(session.scalars(select(User)))


# --- headers -----------------------------------------------------------------

def test_known_ha_user(engine, tmp_path, add_user):
    ana = add_user("Ana", ha_user_id="ha-ana")
    r = addon(engine, tmp_path).get("/whoami", headers=headers("ha-ana"))
    assert r.status_code == 200 and r.json()["id"] == ana.id


def test_unknown_ha_user_is_registered_not_member(engine, tmp_path, session):
    r = addon(engine, tmp_path).get("/whoami", headers=headers("ha-new", display="Dana"))
    assert r.status_code == 200 and r.json()["name"] == "Dana"
    [user] = users(session)
    assert user.ha_user_id == "ha-new" and user.is_member is False


def test_display_name_updated(engine, tmp_path, session, add_user):
    add_user("Ana", ha_user_id="ha-ana")
    c = addon(engine, tmp_path)
    r = c.get("/whoami", headers=headers("ha-ana", display="Ana K."))
    assert r.json()["name"] == "Ana K."


def test_header_wins_over_cookie(engine, tmp_path, add_user):
    ana = add_user("Ana", ha_user_id="ha-ana")
    bor = add_user("Bor")
    c = addon(engine, tmp_path)
    c.get(f"/pick/{bor.id}")
    r = c.get("/whoami", headers=headers("ha-ana"))
    assert r.json()["id"] == ana.id
    # Without headers the cookie is used (add-on fallback).
    assert c.get("/whoami").json()["id"] == bor.id


def test_forged_headers_from_other_address_get_403_and_no_user(engine, tmp_path, session):
    c = addon(engine, tmp_path, host="192.168.1.5")
    r = c.get("/whoami", headers=headers("ha-evil"))
    assert r.status_code == 403
    assert users(session) == []


def test_headers_ignored_in_standalone(engine, tmp_path, session, add_user):
    add_user("Ana", ha_user_id="ha-ana")
    c = build(engine, tmp_path, host=INGRESS_PROXY_ADDRESS)
    r = c.get("/whoami", headers=headers("ha-ana"))
    assert r.status_code == 303 and r.headers["location"] == PICKER_PATH
    assert len(users(session)) == 1


def test_headers_ignored_on_api_listener(engine, tmp_path, session):
    from cekar.app import create_api_app

    token = "t" * 16
    settings = Settings(
        data_dir=tmp_path, mode=Mode.ADDON, api_token=token, api_port=8100
    )
    api = TestClient(
        create_api_app(create_app(settings, engine)),
        client=(INGRESS_PROXY_ADDRESS, 50000),
    )
    r = api.get(
        "/api/v1/health", headers={**headers("ha-evil"), "Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert users(session) == []


def test_blank_header_id_falls_back_to_cookie(engine, tmp_path, add_user):
    bor = add_user("Bor")
    c = addon(engine, tmp_path)
    c.get(f"/pick/{bor.id}")
    assert c.get("/whoami", headers={USER_ID_HEADER: ""}).json()["id"] == bor.id


def test_utf8_display_name(engine, tmp_path):
    h = {k.lower().encode(): v.encode() for k, v in headers("ha-a").items()}
    h[DISPLAY_NAME_HEADER.lower().encode()] = "Anže".encode("utf-8")
    r = addon(engine, tmp_path).get("/whoami", headers=list(h.items()))
    assert r.json()["name"] == "Anže"


# --- picker cookie -----------------------------------------------------------

def test_no_cookie_redirects_to_picker(engine, tmp_path):
    r = build(engine, tmp_path, host="testclient").get("/whoami")
    assert r.status_code == 303 and r.headers["location"] == PICKER_PATH


def test_picker_redirect_honours_ingress_prefix(engine, tmp_path):
    c = addon(engine, tmp_path)
    r = c.get("/whoami", headers={"X-Ingress-Path": "/api/hassio_ingress/abc"})
    assert r.headers["location"] == "/api/hassio_ingress/abc" + PICKER_PATH


def test_cookie_identifies_person_and_flags(engine, tmp_path, add_user):
    ana = add_user("Ana")
    c = build(engine, tmp_path, host="testclient")
    r = c.get(f"/pick/{ana.id}")
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert f"max-age={365 * 24 * 3600}" in cookie
    assert c.get("/whoami").json()["id"] == ana.id


def test_tampered_cookie_ignored(engine, tmp_path, add_user):
    ana = add_user("Ana")
    c = build(engine, tmp_path, host="testclient")
    c.cookies.set(IDENTITY_COOKIE, ana.id)
    assert c.get("/whoami").status_code == 303
    c.cookies.set(IDENTITY_COOKIE, "a.b.c")
    assert c.get("/whoami").status_code == 303


def test_cookie_signed_with_other_secret_ignored(engine, tmp_path, add_user):
    ana = add_user("Ana")
    a = build(engine, tmp_path, host="testclient", secret="one")
    b = build(engine, tmp_path, host="testclient", secret="two")
    a.get(f"/pick/{ana.id}")
    b.cookies.set(IDENTITY_COOKIE, a.cookies[IDENTITY_COOKIE])
    assert b.get("/whoami").status_code == 303


def test_cookie_for_unknown_or_deleted_user_ignored(engine, tmp_path, session, add_user):
    ana = add_user("Ana")
    c = build(engine, tmp_path, host="testclient")
    c.get("/pick/not-a-user")
    assert c.get("/whoami").status_code == 303
    c.get(f"/pick/{ana.id}")
    assert c.get("/whoami").status_code == 200
    sync.soft_delete(session.get(User, ana.id), session)
    session.commit()
    assert c.get("/whoami").status_code == 303


def test_switch_person_clears_cookie(engine, tmp_path, add_user):
    ana = add_user("Ana")
    c = build(engine, tmp_path, host="testclient")
    c.get(f"/pick/{ana.id}")
    c.get("/clear")
    assert c.get("/whoami").status_code == 303


def test_login_comes_before_picker(engine, tmp_path):
    c = build(engine, tmp_path, host="testclient", password="pw")
    r = c.get("/whoami")
    assert r.status_code == 303 and r.headers["location"] == "/login"


# --- session key mixes in the password (group 1 hand-over) --------------------

def test_password_change_invalidates_sessions_with_stored_secret(engine, tmp_path):
    old = build(engine, tmp_path, host="testclient", password="pw", secret="stored")
    old.post("/login", data={"password": "pw"})
    assert old.get(PROTECTED).status_code == 200
    new = build(engine, tmp_path, host="testclient", password="changed", secret="stored")
    new.cookies.set(SESSION_COOKIE, old.cookies[SESSION_COOKIE])
    assert new.get(PROTECTED).status_code == 401


def test_same_password_and_secret_keep_session(engine, tmp_path):
    old = build(engine, tmp_path, host="testclient", password="pw", secret="stored")
    old.post("/login", data={"password": "pw"})
    same = build(engine, tmp_path, host="testclient", password="pw", secret="stored")
    same.cookies.set(SESSION_COOKIE, old.cookies[SESSION_COOKIE])
    assert same.get(PROTECTED).status_code == 200
