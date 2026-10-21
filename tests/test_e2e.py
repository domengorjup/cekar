"""End to end over HTTP: a household shops, splits the receipt, settles, undoes."""

from __future__ import annotations

import re

import pytest

from cekar.auth import INGRESS_PROXY_ADDRESS
from cekar.config import Mode


@pytest.fixture
def ana_and_bor(client_for, two_people, session):
    ana, bor = two_people
    ana.ha_user_id, bor.ha_user_id = "ha-ana", "ha-bor"
    session.commit()
    clients = []
    for ha_id, name in (("ha-ana", "Ana"), ("ha-bor", "Bor")):
        c = client_for(host=INGRESS_PROXY_ADDRESS, mode=Mode.ADDON)
        c.headers["X-Remote-User-Id"] = ha_id
        c.headers["X-Remote-User-Display-Name"] = name
        clients.append(c)
    return clients[0], clients[1], ana, bor


def _id(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    assert match, pattern
    return match.group(1)


def test_shopping_trip_to_settled(ana_and_bor):
    ana, bor_client, _, bor = ana_and_bor

    # Ana starts a list and adds items; one is for Bor.
    created = ana.post("/lists/new", data={"name": "Weekly"})
    list_path = created.headers["location"]
    list_id = list_path.rsplit("/", 1)[1]
    ana.post(f"/lists/{list_id}/items", data={"name": "Milk", "quantity": "2 l"})
    ana.post(f"/lists/{list_id}/items", data={"name": "Razor", "for_whom": bor.id})
    page = ana.get(list_path).text
    assert "Milk" in page and "Razor" in page and "2 l" in page

    # Bor sees the same list and checks both items.
    bor_page = bor_client.get(list_path).text
    item_ids = re.findall(r"/items/([0-9a-f-]{36})/check", bor_page)
    assert len(item_ids) == 2
    for item_id in item_ids:
        assert bor_client.post(f"/items/{item_id}/check", data={"checked": "1"}).status_code == 303
    assert "2 checked items" in bor_client.get(list_path).text

    # Done shopping: Bor paid EUR 30, the razor cost EUR 10 and is for Bor.
    form = bor_client.get(f"/lists/{list_id}/done")
    assert form.status_code == 200 and "Receipt total" in form.text
    price_field = _id(form.text, r'name="(price_[0-9a-f-]{36})"')
    done = bor_client.post(
        f"/lists/{list_id}/done",
        data={"total": "30,00", "date": "2026-10-18", "payer": bor.id, price_field: "10"},
    )
    assert done.status_code == 303 and done.headers["location"].endswith("/expenses?trip=2")
    assert "Nothing on this list yet." in bor_client.get(list_path).text

    # Balance: Bor paid 30 and 20 is shared, so Ana owes Bor EUR 10.
    expenses = ana.get("/expenses").text
    assert "You owe Bor €10.00" in expenses
    assert "€30.00" in expenses

    # Ana settles up in two steps; the second overshoots and gets a warning first.
    settle = {"debtor": _id(expenses, r"debtor=([0-9a-f-]{36})"), "creditor": bor.id,
              "date": "2026-10-19"}
    assert ana.post("/settle", data={**settle, "amount": "4.00"}).status_code == 303
    assert "You owe Bor €6.00" in ana.get("/expenses").text
    warned = ana.post("/settle", data={**settle, "amount": "9.00"})
    assert warned.status_code == 200 and "more than is owed" in warned.text
    again = ana.post("/settle", data={**settle, "amount": "6.00"})
    assert again.status_code == 303
    assert "All settled" in ana.get("/expenses").text


def test_delete_and_undo_of_an_expense(ana_and_bor):
    ana, _, ana_user, bor = ana_and_bor
    ana.post("/expenses/new", data={
        "title": "Internet", "amount": "35.00", "date": "2026-10-17", "payer": ana_user.id,
        "split": "equal", "participants": [ana_user.id, bor.id]})
    expense_id = _id(ana.get("/expenses").text, r"/expenses/([0-9a-f-]{36})/edit")

    deleted = ana.post(f"/expenses/{expense_id}/delete")
    assert deleted.status_code == 303
    page = ana.get(deleted.headers["location"]).text
    assert "Deleted expense Internet" in page and "Undo" in page
    assert "No expenses yet." in page

    restore = _id(page, r'action="([^"]*/expenses/[0-9a-f-]{36}/restore)"')
    assert ana.post(restore).status_code == 303
    assert "Internet" in ana.get("/expenses").text


def test_item_delete_undo_and_clear_checked(ana_and_bor):
    ana, *_ = ana_and_bor
    list_path = ana.post("/lists/new", data={"name": "Weekly"}).headers["location"]
    list_id = list_path.rsplit("/", 1)[1]
    ana.post(f"/lists/{list_id}/items", data={"name": "Eggs"})
    item_id = _id(ana.get(list_path).text, r"/items/([0-9a-f-]{36})/edit")
    deleted = ana.post(f"/items/{item_id}/delete")
    page = ana.get(deleted.headers["location"]).text
    assert "Deleted item Eggs" in page
    ana.post(f"/items/{item_id}/restore")
    assert "Eggs" in ana.get(list_path).text
    ana.post(f"/items/{item_id}/check", data={"checked": "1"})
    ana.post(f"/lists/{list_id}/clear")
    assert "Eggs" not in ana.get(list_path).text


def test_empty_name_is_refused_with_a_message(ana_and_bor):
    ana, *_ = ana_and_bor
    list_path = ana.post("/lists/new", data={"name": "Weekly"}).headers["location"]
    list_id = list_path.rsplit("/", 1)[1]
    bad = ana.post(f"/lists/{list_id}/items", data={"name": "  "})
    assert bad.status_code == 422 and "Enter what to buy." in bad.text
