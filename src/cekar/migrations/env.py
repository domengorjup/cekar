"""Alembic environment; runs on a connection supplied by ``db.run_migrations``."""

from __future__ import annotations

from alembic import context
from sqlalchemy import MetaData

# No feature tables yet. Replace with the declarative Base metadata once models exist.
target_metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

connection = context.config.attributes["connection"]
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,
)
with context.begin_transaction():
    context.run_migrations()
