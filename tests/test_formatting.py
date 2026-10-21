"""Tests for money() and date() (design D10; i18n spec "Formatting")."""

from __future__ import annotations

import datetime as dt

import pytest

from cekar.web.formatting import date, money, month_label, parse_amount


@pytest.mark.parametrize(
    ("cents", "text"),
    [(1250, "€12.50"), (0, "€0.00"), (5, "€0.05"), (4210, "€42.10"),
     (100000, "€1000.00"), (-350, "-€3.50")],
)
def test_money(cents, text):
    assert money(cents) == text


def test_amount_display_scenario():
    assert money(1250) == "€12.50"


def test_date():
    assert date(dt.date(2026, 10, 21)) == "21 Oct 2026"
    assert date(dt.date(2026, 1, 5)) == "5 Jan 2026"


def test_every_month_has_a_name():
    for month in range(1, 13):
        assert date(dt.date(2026, month, 1)).split()[1].isalpha()
        assert month_label(2026, month).endswith(" 2026")


def test_month_label():
    assert month_label(2026, 10) == "October 2026"


def test_amount_input_with_comma_scenario():
    assert parse_amount("12,5") == 1250
    assert parse_amount("12.5") == 1250
