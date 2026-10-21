"""Tests for the optional add-on API listener (ha-addon and web-access specs)."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from cekar import app as app_module
from cekar.app import api_listener_enabled, create_api_app, create_app
from cekar.config import Mode, Settings, load_settings

TOKEN = "t" * 16
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def api_client(engine, tmp_path) -> TestClient:
    """Client for the API listener app (add-on mode, token set)."""
    settings = Settings(
        mode=Mode.ADDON, data_dir=tmp_path, api_token=TOKEN, api_port=8100
    )
    return TestClient(create_api_app(create_app(settings, engine)))


def test_health_with_token(api_client):
    r = api_client.get("/api/v1/health", headers=AUTH)
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_no_header_401(api_client):
    r = api_client.get("/api/v1/health")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_wrong_token_401(api_client):
    r = api_client.get("/api/v1/health", headers={"Authorization": f"Bearer {'x' * 16}"})
    assert r.status_code == 401


@pytest.mark.parametrize("path", ["/", "/static/app.css", "/login", "/docs"])
@pytest.mark.parametrize("headers", [{}, AUTH])
def test_only_api_is_served(api_client, path, headers):
    assert api_client.get(path, headers=headers).status_code == 404


def test_api_cannot_write(api_client):
    assert api_client.post("/api/v1/health", headers=AUTH).status_code == 405


def test_no_token_no_listener(caplog):
    settings = Settings(mode=Mode.ADDON, api_port=8100)
    with caplog.at_level(logging.WARNING, logger="cekar.app"):
        assert api_listener_enabled(settings) is False
    assert "api_token" in caplog.text


def test_token_starts_listener():
    settings = Settings(mode=Mode.ADDON, api_port=8100, api_token=TOKEN)
    assert api_listener_enabled(settings) is True


def test_short_token_fails_startup(tmp_path):
    options = tmp_path / "options.json"
    options.write_text(json.dumps({"api_token": "short"}))
    with pytest.raises(ValueError, match="at least 16"):
        load_settings({"CEKAR_MODE": "addon"}, options_file=options)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, headers: dict[str, str] | None = None) -> int:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_second_listener_over_real_sockets(tmp_path):
    """Both listeners run in one process; the API port serves only /api/v1."""
    port, api_port = _free_port(), _free_port()
    settings = Settings(
        mode=Mode.ADDON, data_dir=tmp_path, host="127.0.0.1", port=port,
        api_port=api_port, api_token=TOKEN,
    )
    thread = threading.Thread(
        target=lambda: asyncio.run(app_module._serve(settings)), daemon=True
    )
    thread.start()  # daemon: ends with the test process
    base = f"http://127.0.0.1:{api_port}"
    for _ in range(100):
        try:
            _get(f"{base}/api/v1/health")
            break
        except OSError:
            time.sleep(0.1)
    assert _get(f"{base}/api/v1/health", AUTH) == 200
    assert _get(f"{base}/api/v1/health") == 401
    assert _get(f"{base}/", AUTH) == 404
    # Ingress port rejects direct (non-proxy) callers in add-on mode.
    assert _get(f"http://127.0.0.1:{port}/") == 403
