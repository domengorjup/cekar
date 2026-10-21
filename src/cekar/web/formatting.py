"""
Show and parse money and dates (design D5, D10). FROZEN SIGNATURES:
``money``, ``date``, ``month_label``, ``parse_amount``.

English style in v1.0: ``€12.50``, ``21 Oct 2026``. Month names come from
the catalog. Group 7 owns the details of ``money`` and ``date`` from here on.
"""

from __future__ import annotations

import datetime as dt
import re

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


def parse_amount(text: str | None) -> int:
    """
    Parse a user-typed euro amount into cents (design D5).

    Accepts ``12,50``, ``12.50``, ``12,5`` and ``12``: at most two decimals,
    a decimal comma or point, no thousands separators. Surrounding spaces
    are ignored.

    Raises
    ------
    ServiceError
        ``error.amount.required`` (blank), ``error.amount.invalid`` (not an
        amount, e.g. ``1,234`` or ``12.``), ``error.amount.too_large`` (more
        than seven digits before the decimal), ``error.amount.not_positive``
        (zero or negative).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise ServiceError("error.amount.required")
    match = _AMOUNT.match(cleaned)
    if match is None:
        raise ServiceError("error.amount.invalid")
    sign, euros, decimals = match.groups()
    if len(euros.lstrip("0")) > _MAX_EURO_DIGITS:
        raise ServiceError("error.amount.too_large")
    cents = int(euros) * 100 + int((decimals or "").ljust(2, "0"))
    if sign or cents == 0:
        raise ServiceError("error.amount.not_positive")
    return cents
