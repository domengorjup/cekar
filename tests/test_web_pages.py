"""Web pages: every screen renders, at the root and under an Ingress prefix."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from cekar.auth import INGRESS_PROXY_ADDRESS
from cekar.config import Mode

WEB = Path(__file__).parent.parent / "src" / "cekar" / "web"
PREFIX = "/api/hassio_ingress/abc123"
LOCAL_URL = re.compile(r"""\b(?:href|src|action|formaction)="(/[^"]*)\"""")
EXTERNAL_URL = re.compile(r"""\b(?:href|src|action|formaction)="(?:https?:)?//""")


@pytest.fixture
def household(client_for, people, session):
    """Ana's client (an Ingress user) with a list, items, an expense and a payment."""
    people.ana.ha_user_id = "ha-ana"
    session.commit()
    client = client_for(host=INGRESS_PROXY_ADDRESS, mode=Mode.ADDON)
    client.headers["X-Remote-User-Id"] = "ha-ana"
    client.headers["X-Remote-User-Display-Name"] = "Ana"
    return client


def _setup(client, people, session):
    session.commit()
    created = client.post("/lists/new", data={"name": "Weekly"})
    assert created.status_code == 303
    list_id = created.headers["location"].rsplit("/", 1)[1]
    client.post(f"/lists/{list_id}/items", data={"name": "Milk", "quantity": "2 l"})
    client.post(f"/lists/{list_id}/items", data={"name": "Bread", "for_whom": people.bor.id})
    expense = client.post(
        "/expenses/new",
        data={"title": "Internet", "amount": "35,00", "date": "2026-10-17",
              "payer": people.ana.id, "split": "equal",
              "participants": [people.ana.id, people.bor.id, people.cene.id]},
    )
    assert expense.status_code == 303
    client.post("/settle", data={"debtor": people.bor.id, "creditor": people.ana.id,
                                 "amount": "5.00", "date": "2026-10-18"})
    return list_id


@pytest.fixture
def pages(household, people, session):
    ana = household
    list_id = _setup(ana, people, session)
    item_id = re.search(r"/items/([0-9a-f-]{36})/edit", ana.get(f"/lists/{list_id}").text).group(1)
    expense_id = re.search(r"/expenses/([0-9a-f-]{36})/edit", ana.get("/expenses").text).group(1)
    payment_id = re.search(r"/payments/([0-9a-f-]{36})/edit", ana.get("/expenses").text).group(1)
    return [
        "/", f"/lists/{list_id}", f"/lists/{list_id}/items", "/lists/new",
        f"/lists/{list_id}/edit", f"/lists/{list_id}/delete", f"/lists/{list_id}/suggest?q=mi",
        f"/items/{item_id}/edit", "/expenses", "/expenses/body", "/expenses/new",
        f"/expenses/{expense_id}/edit",
        f"/settle?debtor={people.bor.id}&creditor={people.ana.id}",
        f"/payments/{payment_id}/edit", "/settings",
    ]


def test_every_page_renders(household, pages):
    for path in pages:
        response = household.get(path)
        assert response.status_code == 200, path
        assert "Traceback" not in response.text


def test_dialogs_render_without_page_chrome(household, pages):
    for path in ("/lists/new", "/expenses/new"):
        full = household.get(path).text
        dialog = household.get(path, headers={"X-Cekar-Dialog": "1"}).text
        assert "<html" in full and "<html" not in dialog
        assert 'role="dialog"' in dialog


def test_urls_follow_the_ingress_prefix_and_stay_local(household, pages):
    for path in pages:
        text = household.get(path, headers={"X-Ingress-Path": PREFIX}).text
        assert not EXTERNAL_URL.search(text), path
        for target in LOCAL_URL.findall(text):
            assert target.startswith(PREFIX + "/"), (path, target)


def test_expenses_page_shows_money_and_balance(household, pages):
    text = household.get("/expenses").text
    assert "€35.00" in text
    assert "Bor owes you" in text
    assert "Internet" in text


def test_who_page_at_both_roots(client, people):
    assert "Ana" in client.get("/who").text
    prefixed = client.get("/who", headers={"X-Ingress-Path": PREFIX}).text
    assert f'action="{PREFIX}/who"' in prefixed


def test_login_template_compiles():
    """auth.py still renders its own page; the template is ready for group 3."""
    from cekar.web.templating import templates

    assert templates.env.get_template("login.html")


def test_web_layer_never_writes_to_the_session_itself():
    """Writes go through services only (design D1)."""
    forbidden = {"add", "add_all", "delete", "commit", "flush", "merge"}
    found = []
    for path in sorted(WEB.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "session"
            ):
                found.append(f"{path.name}:{node.lineno} session.{node.func.attr}")
    assert not found, found


def test_non_member_sees_names_not_you(client_for, people, add_user, session):
    add_user("Tablet", member=False, ha_user_id="ha-tablet")
    c = client_for(host=INGRESS_PROXY_ADDRESS, mode=Mode.ADDON)
    c.headers["X-Remote-User-Id"] = "ha-tablet"
    c.headers["X-Remote-User-Display-Name"] = "Tablet"
    page = c.get("/expenses")
    assert page.status_code == 200
    assert "All settled" in page.text


def test_standalone_picker_adds_a_person_and_settings_can_add_more(client):
    assert client.get("/who").status_code == 200
    added = client.post("/who/add", data={"name": "Ana"}, follow_redirects=False)
    assert added.status_code == 303
    assert client.get("/settings").status_code == 200
    assert client.get("/settings/people/new").status_code == 200
    posted = client.post("/settings/people/new", data={"name": "Bor"}, follow_redirects=False)
    assert posted.status_code == 303
    bad = client.post("/settings/people/new", data={"name": " "})
    assert bad.status_code == 422 and "Enter a name." in bad.text


def test_add_person_hidden_for_home_assistant_users(household):
    assert household.get("/settings/people/new").status_code == 404
    assert "Add person" not in household.get("/settings").text


def test_list_switcher_is_a_polled_region(household, people, session):
    list_id = _setup(household, people, session)
    page = household.get(f"/lists/{list_id}").text
    assert "data-live-chips" in page
    assert f'data-fragment-url="{"/lists/" + list_id + "/chips"}"' in page

    version = household.get("/lists/version")
    assert version.status_code == 200 and version.text.isdigit()
    chips = household.get(f"/lists/{list_id}/chips")
    assert chips.status_code == 200
    assert "<html" not in chips.text and "Weekly" in chips.text
    assert f'data-version="{version.text}"' in chips.text


def test_list_switcher_follows_other_users_changes(household, people, session):
    list_id = _setup(household, people, session)
    before = household.get("/lists/version").text
    created = household.post("/lists/new", data={"name": "Hardware"})
    new_id = created.headers["location"].rsplit("/", 1)[1]
    household.post(f"/lists/{new_id}/items", data={"name": "Nails"})
    assert household.get("/lists/version").text != before
    chips = household.get(f"/lists/{list_id}/chips").text
    assert "Hardware" in chips
    household.post(f"/lists/{new_id}/delete")
    assert "Hardware" not in household.get(f"/lists/{list_id}/chips").text


def test_phone_header_only_dropped_in_addon_mode(household, client, people, session):
    # Add-on mode: body is marked, Settings shows who is signed in.
    assert 'class="embedded"' in household.get("/settings").text
    assert "Signed in as" in household.get("/settings").text
    # Standalone keeps its header and its picker row.
    session.commit()
    client.post("/who", data={"user_id": people.ana.id})
    standalone = client.get("/settings")
    assert 'class="embedded"' not in standalone.text
    assert "Signed in as" not in standalone.text
