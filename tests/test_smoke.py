"""Smoke tests: the app starts and serves its basic pages."""

from __future__ import annotations

from cekar import __version__
from cekar.app import create_app
from cekar.config import Settings


def test_who_page_renders_without_a_user(client):
    r = client.get("/who")
    assert r.status_code == 200
    assert "Who are you?" in r.text
    assert "Cekar" in r.text


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_static_assets_served(client):
    for name in ("app.css", "app.js", "theme.js", "icons.svg"):
        assert client.get(f"/static/{name}").status_code == 200


def test_base_path_from_ingress_header(client):
    prefix = "/api/hassio_ingress/abc"
    r = client.get("/who", headers={"X-Ingress-Path": prefix})
    assert f'href="{prefix}/static/app.css"' in r.text


def test_base_path_from_settings(engine, tmp_path):
    from fastapi.testclient import TestClient

    app = create_app(Settings(data_dir=tmp_path, base_path="/sub"), engine)
    with TestClient(app) as c:
        assert 'href="/sub/static/app.css"' in c.get("/who").text


def test_invalid_ingress_header_ignored(client):
    r = client.get("/who", headers={"X-Ingress-Path": "/x'><script>"})
    assert "<script>" not in r.text.split("</head>")[1]
    assert 'href="/static/app.css"' in r.text


def test_version():
    assert __version__ == "0.0.1"
