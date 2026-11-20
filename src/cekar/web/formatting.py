"""
Show and parse money and dates (design D5, D10). FROZEN SIGNATURES:
``money``, ``date``, ``month_label``, ``parse_amount``.

English style in v1.0: ``€12.50``, ``21 Oct 2026``. Month names come from
the catalog. Group 7 owns the details of ``money`` and ``date`` from here on.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from fractions import Fraction

from cekar.i18n import t
from cekar.services import ServiceError

CURRENCY_SYMBOL = "€"  # EUR is fixed

# Optional minus (rejected as not positive), whole euros, optional decimal
# comma or point with one or two digits. No thousands separators.
_AMOUNT = re.compile(r"^(-?)([0-9]+)(?:[.,]([0-9]{1,2}))?$")
_MAX_EURO_DIGITS = 7  # up to EUR 9,999,999.99; longer input is a typo


def format_cents(cents: int) -> str:
    """Return ``1250`` as ``"12.50"`` (form inputs; no currency symbol)."""
    sign = "-" if cents < 0 else ""
    euros, rest = divmod(abs(cents), 100)
    return f"{sign}{euros}.{rest:02d}"


def money(cents: int) -> str:
    """Return cents as ``"€12.50"`` (``"-€3.50"`` when negative)."""
    text = format_cents(cents)
    if text.startswith("-"):
        return f"-{CURRENCY_SYMBOL}{text[1:]}"
    return f"{CURRENCY_SYMBOL}{text}"


def date(day: dt.date) -> str:
    """Return ``21 Oct 2026`` (short month name from the catalog)."""
    return f"{day.day} {t(f'date.month_short.{day.month}')} {day.year}"


def month_label(year: int, month: int) -> str:
    """Return ``October 2026`` (month heading of the expense list)."""
    return f"{t(f'date.month.{month}')} {year}"


_NUMBER = re.compile(r"[0-9]+(?:[.,][0-9]+)?")
_OPERATORS = frozenset("+-*/()")
_MAX_EXPRESSION_LENGTH = 200  # also keeps the recursion shallow


class _Calculator:
    """Recursive-descent evaluator for ``+ - * /``, unary minus, parentheses."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0

    def evaluate(self) -> Fraction:
        """Return the exact value of the whole text."""
        value = self._sum()
        if self._pos != len(self._text):
            raise ServiceError("error.amount.expression")
        return value

    def _peek(self) -> str:
        return self._text[self._pos : self._pos + 1]

    def _sum(self) -> Fraction:
        value = self._product()
        while self._peek() in ("+", "-"):
            sign = self._text[self._pos]
            self._pos += 1
            term = self._product()
            value = value + term if sign == "+" else value - term
        return value

    def _product(self) -> Fraction:
        value = self._unary()
        while self._peek() in ("*", "/"):
            sign = self._text[self._pos]
            self._pos += 1
            factor = self._unary()
            if sign == "*":
                value *= factor
            elif factor == 0:
                raise ServiceError("error.amount.divide_by_zero")
            else:
                value /= factor
        return value

    def _unary(self) -> Fraction:
        if self._peek() == "-":
            self._pos += 1
            return -self._unary()
        return self._atom()

    def _atom(self) -> Fraction:
        if self._peek() == "(":
            self._pos += 1
            value = self._sum()
            if self._peek() != ")":
                raise ServiceError("error.amount.expression")
            self._pos += 1
            return value
        match = _NUMBER.match(self._text, self._pos)
        if match is None:
            raise ServiceError("error.amount.expression")
        self._pos = match.end()
        return Fraction(match.group().replace(",", "."))


def _evaluate_cents(text: str) -> int:
    """Return the signed cents of a plain amount or a calculation."""
    cleaned = text.strip()
    if cleaned.startswith("="):
        cleaned = cleaned[1:].strip()
    match = _AMOUNT.match(cleaned)
    if match is not None:
        sign, euros, decimals = match.groups()
        cents = int(euros) * 100 + int((decimals or "").ljust(2, "0"))
        return -cents if sign else cents
    if not _OPERATORS.intersection(cleaned):
        raise ServiceError("error.amount.invalid")
    if len(cleaned) > _MAX_EXPRESSION_LENGTH:
        raise ServiceError("error.amount.expression")
    value = _Calculator(cleaned.replace(" ", "")).evaluate() * 100
    return math.floor(value + Fraction(1, 2))  # halves round up


def parse_amount(text: str | None, *, allow_zero: bool = False) -> int:
    """
    Parse a user-typed euro amount or calculation into cents (design D5).

    A plain number accepts ``12,50``, ``12.50``, ``12,5`` and ``12``: at most
    two decimals, a decimal comma or point, no thousands separators. A
    calculation (optional leading ``=``) uses numbers with any number of
    decimals, ``+ - * /``, unary minus and parentheses, e.g.
    ``=12,40+3,10`` or ``1,299*0,75``. It is evaluated exactly and rounded
    to whole cents, halves up. Spaces around the text are ignored, and
    spaces inside a calculation too.

    Parameters
    ----------
    text : str | None
        The typed text.
    allow_zero : bool, optional
        Return 0 instead of raising for a zero result (exact split shares).

    Raises
    ------
    ServiceError
        ``error.amount.required`` (blank), ``error.amount.invalid`` (not an
        amount, e.g. ``1,234`` or ``12.``), ``error.amount.expression``
        (malformed calculation), ``error.amount.divide_by_zero``,
        ``error.amount.too_large`` (more than seven digits before the
        decimal), ``error.amount.not_positive`` (zero or negative).
    """
    if not (text or "").strip().lstrip("=").strip():
        raise ServiceError("error.amount.required")
    cents = _evaluate_cents(text)
    if cents == 0 and allow_zero:
        return 0
    if cents <= 0:
        raise ServiceError("error.amount.not_positive")
    if cents >= 10 ** (_MAX_EURO_DIGITS + 2):
        raise ServiceError("error.amount.too_large")
    return cents
