"""Tests for parse_amount (design D5 input) and split_equal (D5 rounding)."""

from __future__ import annotations

import pytest

from cekar.services import ServiceError
from cekar.services.expenses import split_equal
from cekar.web.formatting import parse_amount


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("12,50", 1250), ("12.50", 1250), ("12,5", 1250), ("12", 1200),
        (" 7.05 ", 705), ("0,01", 1), ("0.10", 10), ("24.90", 2490),
        ("9999999.99", 999999999),
    ],
)
def test_parse_amount_valid(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("", "error.amount.required"),
        ("   ", "error.amount.required"),
        (None, "error.amount.required"),
        ("0", "error.amount.not_positive"),
        ("0,00", "error.amount.not_positive"),
        ("-3", "error.amount.not_positive"),
        ("-0", "error.amount.not_positive"),
        ("1,234", "error.amount.invalid"),
        ("1.234,50", "error.amount.invalid"),
        ("1 234", "error.amount.invalid"),
        ("12.", "error.amount.invalid"),
        (",5", "error.amount.invalid"),
        ("12,50 €", "error.amount.invalid"),
        ("abc", "error.amount.invalid"),
        ("1e3", "error.amount.invalid"),
        ("١٢", "error.amount.invalid"),  # non-ASCII digits
        ("10000000", "error.amount.too_large"),
    ],
)
def test_parse_amount_invalid(text, key):
    with pytest.raises(ServiceError) as raised:
        parse_amount(text)
    assert raised.value.key == key


# --- split_equal: every rounding scenario of the expenses spec ------------------

ORDER = ["ana", "bor", "cene"]


def test_odd_cent_two_members_goes_to_payer():
    shares = split_equal(1001, ["ana", "bor"], payer="ana", order=ORDER)
    assert shares == {"ana": 501, "bor": 500}


def test_odd_cent_when_the_later_member_pays():
    shares = split_equal(1001, ["ana", "bor"], payer="bor", order=ORDER)
    assert shares == {"bor": 501, "ana": 500}


def test_three_members():
    shares = split_equal(1000, ["ana", "bor", "cene"], payer="ana", order=ORDER)
    assert shares == {"ana": 334, "bor": 333, "cene": 333}


def test_three_members_two_extra_cents_payer_in_the_middle():
    shares = split_equal(1001, ["cene", "ana", "bor"], payer="bor", order=ORDER)
    assert shares == {"bor": 334, "ana": 334, "cene": 333}
    assert list(shares) == ["bor", "ana", "cene"]


def test_payer_not_participating():
    shares = split_equal(1001, ["bor", "cene"], payer="ana", order=ORDER)
    assert shares == {"bor": 501, "cene": 500}


def test_even_amount_has_no_remainder():
    assert split_equal(3000, ["ana", "bor"], "ana", ORDER) == {"ana": 1500, "bor": 1500}


def test_single_participant_carries_everything():
    assert split_equal(999, ["bor"], "ana", ORDER) == {"bor": 999}


def test_amount_smaller_than_participants_gives_zero_shares():
    assert split_equal(2, ["ana", "bor", "cene"], "cene", ORDER) == {
        "cene": 1, "ana": 1, "bor": 0,
    }


@pytest.mark.parametrize("amount", [1, 2, 3, 99, 100, 101, 1001, 123457])
@pytest.mark.parametrize("payer", ["ana", "bor", "cene", "dan"])
def test_shares_always_sum_and_differ_by_at_most_one(amount, payer):
    shares = split_equal(amount, ["ana", "bor", "cene"], payer, ORDER)
    assert sum(shares.values()) == amount
    assert max(shares.values()) - min(shares.values()) <= 1


@pytest.mark.parametrize(
    ("amount", "participants"),
    [(0, ["ana"]), (-5, ["ana"]), (100, []), (100, ["ana", "ana"]), (100, ["zoe"])],
)
def test_split_equal_rejects_bad_calls(amount, participants):
    with pytest.raises(ValueError):
        split_equal(amount, participants, "ana", ORDER)


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("=12,40+3,10", 1550), ("12.40 + 3.10", 1550), ("= 12,40 + 3,10", 1550),
        ("=3*2,49-1", 647), ("(10+5)/3", 500), ("2+3*4", 1400), ("(2+3)*4", 2000),
        ("20-(-5)", 2500), ("-(2-5)", 300), ("--3+0", 300), ("10/4", 250),
        ("1,299*0,75", 97),      # 0.97425
        ("0,125*0,1+0", 1),      # 0.0125 -> 1.25 cents
        ("0,005*100+0", 50), ("0,0049+0,005", 1), ("1/3*3", 100),
        ("0,745+0", 75),         # 74.5 cents: halves round up
    ],
)
def test_parse_amount_calculation(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("12+", "error.amount.expression"), ("2**3", "error.amount.expression"),
        ("(1+2", "error.amount.expression"), ("1+2)", "error.amount.expression"),
        ("2^3+1", "error.amount.expression"), ("a+1", "error.amount.expression"),
        ("1,2,3+1", "error.amount.expression"), ("()", "error.amount.expression"),
        ("1+" * 120 + "1", "error.amount.expression"),
        ("10/0", "error.amount.divide_by_zero"), ("1/(2-2)", "error.amount.divide_by_zero"),
        ("5-5", "error.amount.not_positive"), ("2-3", "error.amount.not_positive"),
        ("0,001*2", "error.amount.not_positive"),
        ("9999999,99+1", "error.amount.too_large"), ("10000000*1", "error.amount.too_large"),
        ("1,234", "error.amount.invalid"), ("=1,234", "error.amount.invalid"),
        ("1 234", "error.amount.invalid"), ("abc", "error.amount.invalid"),
        ("=", "error.amount.required"),
    ],
)
def test_parse_amount_calculation_errors(text, key):
    with pytest.raises(ServiceError) as caught:
        parse_amount(text)
    assert caught.value.key == key


def test_parse_amount_allow_zero_for_exact_shares():
    assert parse_amount("2-2", allow_zero=True) == 0
    assert parse_amount("0,00", allow_zero=True) == 0
    assert parse_amount("2+2", allow_zero=True) == 400
