"""Tests for services/suggestions.py (suggestions scenarios of the shopping-lists spec)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from cekar.services import lists, suggestions

NOW = datetime(2026, 10, 1, 12, 0, 0)


@pytest.fixture
def shopping(session, people):
    shopping = lists.create_list(session, people.ana.id, "Groceries")
    session.flush()
    return shopping


def use(session, people, shopping, name, days_ago, times=1, *, clear=True):
    """Add ``name`` ``times`` times, each dated ``days_ago`` days before NOW."""
    for _ in range(times):
        item = lists.add_item(session, people.ana.id, shopping.id, name).item
        item.created_at = NOW - timedelta(days=days_ago)
        lists.set_checked(session, people.ana.id, item.id, True)
        if clear:
            lists.clear_checked(session, people.ana.id, shopping.id)
    session.flush()


def names(session, shopping, query, **kw):
    return [s.name for s in suggestions.suggest(session, shopping.id, query, NOW, **kw)]


def test_frequent_and_recent_first(session, people, shopping):
    use(session, people, shopping, "Millet", 365, times=2)
    use(session, people, shopping, "Milk", 10, times=20)
    assert names(session, shopping, "mi") == ["Milk", "Millet"]


def test_accent_insensitive(session, people, shopping):
    use(session, people, shopping, "Čaj", 5)
    assert names(session, shopping, "caj") == ["Čaj"]
    assert names(session, shopping, "ČAJ") == ["Čaj"]


def test_deleted_mistake_not_suggested(session, people, shopping):
    item = lists.add_item(session, people.ana.id, shopping.id, "Mlik").item
    lists.delete_item(session, people.ana.id, item.id)
    assert names(session, shopping, "ml") == []


def test_starts_with_before_contains(session, people, shopping):
    use(session, people, shopping, "Oat milk", 1, times=10)
    use(session, people, shopping, "Milk", 60, times=1)
    assert names(session, shopping, "mi") == ["Milk", "Oat milk"]


def test_ties_by_name(session, people, shopping):
    use(session, people, shopping, "Beans", 3)
    use(session, people, shopping, "Basil", 3)
    assert names(session, shopping, "b") == ["Basil", "Beans"]


def test_unchecked_on_list_left_out(session, people, shopping):
    use(session, people, shopping, "Bread", 3)
    lists.add_item(session, people.ana.id, shopping.id, "Bread")
    assert names(session, shopping, "br") == []


def test_checked_on_list_still_suggested(session, people, shopping):
    use(session, people, shopping, "Bread", 3, clear=False)
    assert names(session, shopping, "br") == ["Bread"]


def test_other_list_unchecked_not_excluded(session, people, shopping):
    other = lists.create_list(session, people.ana.id, "Hardware store")
    lists.add_item(session, people.ana.id, other.id, "Nails")
    assert names(session, shopping, "na") == ["Nails"]


def test_most_recent_spelling(session, people, shopping):
    use(session, people, shopping, "yogurt", 30)
    use(session, people, shopping, "Yogurt", 2)
    result = suggestions.suggest(session, shopping.id, "yog", NOW)
    assert [(s.name, s.name_key) for s in result] == [("Yogurt", "yogurt")]


def test_blank_query_and_limit(session, people, shopping):
    for n in range(10):
        use(session, people, shopping, f"Item {n}", 1)
    assert names(session, shopping, "  ") == []
    assert len(names(session, shopping, "item")) == suggestions.SUGGESTION_LIMIT
    assert len(names(session, shopping, "item", limit=3)) == 3


def test_percent_in_query_is_literal(session, people, shopping):
    use(session, people, shopping, "Milk", 1)
    assert names(session, shopping, "%") == []
