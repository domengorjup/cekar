"""
Message catalog: ``t`` and ``tn`` (design D10). FROZEN SIGNATURES.

v1.0 ships English only (``i18n/en.toml``). The catalog is read once at
import with ``tomllib``; nested TOML tables become flat dotted keys. A
missing key or placeholder raises ``KeyError``, so mistakes surface.
Group 7 completes the machinery (plural rule table, catalog tests).
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path

CATALOG_DIR = Path(__file__).parent / "i18n"
LANGUAGE = "en"

# Language -> function from a count to its plural category.
PLURAL_RULES: dict[str, Callable[[int], str]] = {
    "en": lambda n: "one" if n == 1 else "other",
}


def _flatten(table: dict, prefix: str = "") -> dict[str, str]:
    """Turn nested TOML tables into ``{"a.b.c": "text"}``."""
    flat: dict[str, str] = {}
    for name, value in table.items():
        key = f"{prefix}{name}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{key}."))
        elif isinstance(value, str):
            flat[key] = value
        else:
            raise ValueError(f"catalog entry {key!r} must be a string")
    return flat


def load_catalog(language: str = LANGUAGE) -> dict[str, str]:
    """Read ``i18n/<language>.toml`` and return its flat key -> text mapping."""
    with (CATALOG_DIR / f"{language}.toml").open("rb") as file:
        return _flatten(tomllib.load(file))


CATALOG: dict[str, str] = load_catalog()


def t(key: str, **params: object) -> str:
    """
    Return the message for ``key`` with ``{name}`` placeholders filled in.

    Raises
    ------
    KeyError
        If the key is not in the catalog or a placeholder has no value.
    """
    return CATALOG[key].format(**params)


def tn(key: str, n: int, **params: object) -> str:
    """
    Return the plural form of ``key`` for the count ``n``.

    Looks up ``<key>.<category>`` (English: ``one`` or ``other``) and passes
    ``n`` as the ``{n}`` placeholder, e.g. ``tn("list.checked_items", 2)``
    gives "2 checked items".
    """
    category = PLURAL_RULES[LANGUAGE](n)
    return t(f"{key}.{category}", n=n, **params)
