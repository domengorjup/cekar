"""Tests for the foundation: schema, generated secret, catalog stub, error text."""

from __future__ import annotations

import importlib

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from cekar.app import create_app
from cekar.config import Settings
from cekar.db import SECRET_SETTING, make_engine
from cekar.i18n import CATALOG, t, tn
from cekar.models import Base, Setting
from cekar.services import ServiceError, ServiceWarning
from cekar.web.common import error_text

SERVICE_MODULES = ["sync", "members", "lists", "suggestions", "expenses", "balances", "trips"]


def test_migration_matches_models(engine):
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_schema_indexes(engine):
    inspector = inspect(engine)
    item = {ix["name"]: ix["column_names"] for ix in inspector.get_indexes("item")}
    assert item["ix_item_list_id_deleted_at_cleared_at"] == ["list_id", "deleted_at", "cleared_at"]
    assert item["ix_item_deleted_at_name_key"] == ["deleted_at", "name_key"]
    shares = {ix["name"]: ix for ix in inspector.get_indexes("expense_share")}
    assert shares["ix_expense_share_user_id"]["column_names"] == ["user_id"]
    assert shares["uq_expense_share_live"]["unique"]
    for table in ("user", "user_preference", "shopping_list", "item", "expense",
                  "expense_share", "payment", "shopping_trip"):
        columns = {c["name"] for c in inspector.get_columns(table)}
        assert {"id", "created_at", "updated_at", "deleted_at", "seq"} <= columns
        assert f"ix_{table}_seq" in {ix["name"] for ix in inspector.get_indexes(table)}


def test_secret_generated_once_and_kept(tmp_path):
    engine = make_engine(tmp_path)
    first = create_app(Settings(data_dir=tmp_path), engine).state.settings.secret
    second = create_app(Settings(data_dir=tmp_path), engine).state.settings.secret
    assert first and first == second
    engine.dispose()
    # A restart with a new engine on the same data dir reads the same secret.
    again = make_engine(tmp_path)
    assert create_app(Settings(data_dir=tmp_path), again).state.settings.secret == first
    again.dispose()


def test_configured_secret_wins(tmp_path, engine):
    app = create_app(Settings(data_dir=tmp_path, secret="from-env"), engine)
    assert app.state.settings.secret == "from-env"
    with engine.connect() as connection:
        assert connection.execute(Setting.__table__.select()).all() == []
    assert SECRET_SETTING == "secret"


def test_catalog_lookup_and_placeholders():
    assert t("app.name") == "Cekar"
    assert t("error.list.name_too_long", max_length=50).endswith("50 characters.")
    assert t("date.month_short.10") == "Oct"
    with pytest.raises(KeyError):
        t("no.such.key")
    with pytest.raises(KeyError):
        t("error.list.name_too_long")


def test_tn_picks_english_plural(monkeypatch):
    monkeypatch.setitem(CATALOG, "test.items.one", "{n} item")
    monkeypatch.setitem(CATALOG, "test.items.other", "{n} items")
    assert tn("test.items", 1) == "1 item"
    assert tn("test.items", 2) == "2 items"
    assert tn("test.items", 0) == "0 items"


def test_error_text_formats_money_params():
    assert error_text(ServiceError("error.expense.exact_left", left_cents=500)) == (
        "€5.00 left. The amounts must add up to the total."
    )
    warning = ServiceWarning("warning.payment.overpay", {"owed_cents": 1000, "excess_cents": 500})
    assert error_text(warning).startswith("This is €5.00 more than is owed (€10.00).")
    assert error_text(ServiceError("error.person.name_taken", name="Ana")).startswith("Ana ")


def test_service_error_carries_key_and_params():
    error = ServiceError("error.item.name_too_long", max_length=100)
    assert (error.key, error.params, str(error)) == (
        "error.item.name_too_long", {"max_length": 100}, "error.item.name_too_long",
    )


def test_error_keys_in_service_docstrings_exist():
    """Every ``error.*`` / ``warning.*`` key named by a service stub is in the catalog."""
    import re

    keys = set()
    for name in SERVICE_MODULES:
        module = importlib.import_module(f"cekar.services.{name}")
        source = inspect_source(module)
        keys |= set(re.findall(r"``((?:error|warning)\.[a-z_.]+[a-z])``", source))
    keys |= {"error.amount.required", "error.amount.invalid", "error.amount.too_large"}
    assert keys and sorted(k for k in keys if k not in CATALOG) == []


def inspect_source(module) -> str:
    import inspect as pyinspect

    return pyinspect.getsource(module)


@pytest.mark.parametrize("name", SERVICE_MODULES + ["identity"])
def test_modules_import(name):
    module = "cekar.identity" if name == "identity" else f"cekar.services.{name}"
    assert importlib.import_module(module)
