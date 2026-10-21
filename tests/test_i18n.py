"""Catalog tests (design D10, tasks 7.4): key usage, plurals, placeholders."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from string import Formatter

import pytest

from cekar import i18n
from cekar.i18n import CATALOG, t, tn
from cekar.web.templating import templates

SRC = Path(i18n.__file__).parent
CALL_NAMES = {"t", "tn", "ServiceError", "ServiceWarning"}
PLURAL_CATEGORIES = {"one", "other"}


def _placeholders(message: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(message) if name}


def _param_name(name: str) -> str:
    """Services pass money as ``<name>_cents``; the message uses ``<name>``."""
    return name.removesuffix("_cents")


def _python_calls():
    """Yield (where, function, key, kwarg names) for literal-key calls in src/."""
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name not in CALL_NAMES or not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue  # dynamic key (e.g. a variable); checked where it is built
            kwargs = {k.arg for k in node.keywords if k.arg}
            has_star = any(k.arg is None for k in node.keywords)
            if len(node.args) > 1:  # ServiceWarning(key, {"name": ...})
                params = node.args[1]
                if isinstance(params, ast.Dict) and all(
                    isinstance(k, ast.Constant) for k in params.keys
                ):
                    kwargs |= {k.value for k in params.keys}
                else:
                    has_star = True
            yield (f"{path.relative_to(SRC)}:{node.lineno}", name, first.value,
                   None if has_star else kwargs)


_TEMPLATE_CALL = re.compile(r"""\b(tn|t)\(\s*(['"])([^'"]+)\2""")


def _call_args(text: str, start: int) -> str:
    """Return the text of a call's arguments, from just after its opening paren."""
    depth = 1
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start:i]
    return text[start:]


def _template_calls():
    for path in sorted(SRC.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for match in _TEMPLATE_CALL.finditer(text):
            open_paren = text.index("(", match.start())
            args = _call_args(text, open_paren + 1)
            kwargs = set(re.findall(r"(?:^|,)\s*(\w+)\s*=(?!=)", args))
            line = text.count("\n", 0, match.start()) + 1
            yield f"{path.relative_to(SRC)}:{line}", match.group(1), match.group(3), kwargs


def _all_calls():
    yield from _python_calls()
    yield from _template_calls()


def _messages(key: str, func: str) -> list[str]:
    if func == "tn":
        return [CATALOG[f"{key}.{c}"] for c in sorted(PLURAL_CATEGORIES)
                if f"{key}.{c}" in CATALOG]
    return [CATALOG[key]] if key in CATALOG else []


def test_every_used_key_exists_in_catalog():
    missing = []
    for where, func, key, _ in _all_calls():
        if func == "tn":
            absent = [f"{key}.{c}" for c in sorted(PLURAL_CATEGORIES)
                      if f"{key}.{c}" not in CATALOG]
            if absent:
                missing.append(f"{where}: tn() needs {', '.join(absent)}")
        elif key not in CATALOG:
            missing.append(f"{where}: {func}({key!r}) is not in en.toml")
    assert not missing, "Missing catalog keys:\n  " + "\n  ".join(missing)


def test_used_placeholders_match_call_parameters():
    problems = []
    for where, func, key, kwargs in _all_calls():
        if kwargs is None:
            continue  # **params: cannot be checked statically
        given = {_param_name(k) for k in kwargs}
        if func == "tn":
            given.add("n")
        for message in _messages(key, func):
            needed = _placeholders(message)
            if needed != given:
                problems.append(
                    f"{where}: {key!r} needs {sorted(needed)}, call gives {sorted(given)}")
    assert not problems, "Placeholder mismatch:\n  " + "\n  ".join(problems)


def test_plural_keys_have_one_and_other():
    stems: dict[str, set[str]] = {}
    for key in CATALOG:
        stem, _, last = key.rpartition(".")
        if last in PLURAL_CATEGORIES:
            stems.setdefault(stem, set()).add(last)
    broken = {s: sorted(PLURAL_CATEGORIES - c) for s, c in stems.items()
              if c != PLURAL_CATEGORIES}
    assert not broken, f"Plural keys missing forms: {broken}"


def test_catalog_messages_are_well_formed():
    for key, message in CATALOG.items():
        try:
            _placeholders(message)
        except ValueError as error:
            pytest.fail(f"{key}: bad placeholder syntax: {error}")


def test_month_names_complete():
    for prefix in ("date.month", "date.month_short"):
        for month in range(1, 13):
            assert f"{prefix}.{month}" in CATALOG, f"missing {prefix}.{month}"


# Scenarios of the i18n spec


def test_english_plural_scenario(monkeypatch):
    monkeypatch.setitem(CATALOG, "test.checked.one", "{n} checked item")
    monkeypatch.setitem(CATALOG, "test.checked.other", "{n} checked items")
    assert tn("test.checked", 1) == "1 checked item"
    assert tn("test.checked", 2) == "2 checked items"
    assert tn("test.checked", 0) == "0 checked items"


def test_t_fills_placeholders(monkeypatch):
    monkeypatch.setitem(CATALOG, "test.hello", "Hi {name}")
    assert t("test.hello", name="Ana") == "Hi Ana"


def test_missing_key_raises():
    with pytest.raises(KeyError):
        t("no.such.key")


def test_missing_placeholder_value_raises(monkeypatch):
    monkeypatch.setitem(CATALOG, "test.hello", "Hi {name}")
    with pytest.raises(KeyError):
        t("test.hello")


def test_missing_plural_form_raises():
    with pytest.raises(KeyError):
        tn("no.such.plural", 2)


def test_english_plural_rule():
    rule = i18n.PLURAL_RULES["en"]
    assert [rule(n) for n in (0, 1, 2, 21)] == ["other", "one", "other", "other"]


def test_no_language_controls_in_catalog():
    assert not [k for k in CATALOG if k.startswith(("language", "lang."))]


def test_jinja_globals_bound():
    for name in ("t", "tn", "money", "date"):
        assert name in templates.env.globals
