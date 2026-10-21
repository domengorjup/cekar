"""Initial schema (design D12, D13).

Revision ID: 0001
Revises:
Create Date: 2026-10-21 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('change_counter',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_change_counter'))
    )
    op.create_table('setting',
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_setting'))
    )
    op.create_table('shopping_list',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shopping_list'))
    )
    op.create_index(op.f('ix_shopping_list_seq'), 'shopping_list', ['seq'], unique=False)
    op.create_table('user',
    sa.Column('ha_user_id', sa.String(length=64), nullable=True),
    sa.Column('username', sa.String(length=100), nullable=True),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('is_member', sa.Boolean(), nullable=False),
    sa.Column('member_since', sa.DateTime(), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
    sa.UniqueConstraint('ha_user_id', name=op.f('uq_user_ha_user_id'))
    )
    op.create_index(op.f('ix_user_seq'), 'user', ['seq'], unique=False)
    op.create_table('item',
    sa.Column('list_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('name_key', sa.String(length=100), nullable=False),
    sa.Column('quantity', sa.String(length=30), nullable=True),
    sa.Column('for_whom_id', sa.String(length=36), nullable=True),
    sa.Column('added_by_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('checked_at', sa.DateTime(), nullable=True),
    sa.Column('checked_by_id', sa.String(length=36), nullable=True),
    sa.Column('cleared_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['added_by_id'], ['user.id'], name=op.f('fk_item_added_by_id_user')),
    sa.ForeignKeyConstraint(['checked_by_id'], ['user.id'], name=op.f('fk_item_checked_by_id_user')),
    sa.ForeignKeyConstraint(['for_whom_id'], ['user.id'], name=op.f('fk_item_for_whom_id_user')),
    sa.ForeignKeyConstraint(['list_id'], ['shopping_list.id'], name=op.f('fk_item_list_id_shopping_list')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_item'))
    )
    op.create_index('ix_item_deleted_at_name_key', 'item', ['deleted_at', 'name_key'], unique=False)
    op.create_index('ix_item_list_id_deleted_at_cleared_at', 'item', ['list_id', 'deleted_at', 'cleared_at'], unique=False)
    op.create_index(op.f('ix_item_seq'), 'item', ['seq'], unique=False)
    op.create_table('payment',
    sa.Column('from_user_id', sa.String(length=36), nullable=False),
    sa.Column('to_user_id', sa.String(length=36), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('paid_on', sa.Date(), nullable=False),
    sa.Column('created_by_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], name=op.f('fk_payment_created_by_id_user')),
    sa.ForeignKeyConstraint(['from_user_id'], ['user.id'], name=op.f('fk_payment_from_user_id_user')),
    sa.ForeignKeyConstraint(['to_user_id'], ['user.id'], name=op.f('fk_payment_to_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment'))
    )
    op.create_index(op.f('ix_payment_seq'), 'payment', ['seq'], unique=False)
    op.create_table('shopping_trip',
    sa.Column('list_id', sa.String(length=36), nullable=False),
    sa.Column('payer_id', sa.String(length=36), nullable=False),
    sa.Column('total_cents', sa.Integer(), nullable=False),
    sa.Column('spent_on', sa.Date(), nullable=False),
    sa.Column('created_by_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], name=op.f('fk_shopping_trip_created_by_id_user')),
    sa.ForeignKeyConstraint(['list_id'], ['shopping_list.id'], name=op.f('fk_shopping_trip_list_id_shopping_list')),
    sa.ForeignKeyConstraint(['payer_id'], ['user.id'], name=op.f('fk_shopping_trip_payer_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shopping_trip'))
    )
    op.create_index(op.f('ix_shopping_trip_seq'), 'shopping_trip', ['seq'], unique=False)
    op.create_table('user_preference',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('key', sa.String(length=50), nullable=False),
    sa.Column('value', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_preference_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_preference')),
    sa.UniqueConstraint('user_id', 'key', name=op.f('uq_user_preference_user_id'))
    )
    op.create_index(op.f('ix_user_preference_seq'), 'user_preference', ['seq'], unique=False)
    op.create_table('expense',
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('spent_on', sa.Date(), nullable=False),
    sa.Column('payer_id', sa.String(length=36), nullable=False),
    sa.Column('split', sa.Enum('equal', 'exact', 'for_other', 'personal', name='split', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('trip_id', sa.String(length=36), nullable=True),
    sa.Column('created_by_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.CheckConstraint("split IN ('equal', 'exact', 'for_other', 'personal')", name=op.f('ck_expense_split')),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], name=op.f('fk_expense_created_by_id_user')),
    sa.ForeignKeyConstraint(['payer_id'], ['user.id'], name=op.f('fk_expense_payer_id_user')),
    sa.ForeignKeyConstraint(['trip_id'], ['shopping_trip.id'], name=op.f('fk_expense_trip_id_shopping_trip')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expense'))
    )
    op.create_index(op.f('ix_expense_seq'), 'expense', ['seq'], unique=False)
    op.create_index(op.f('ix_expense_trip_id'), 'expense', ['trip_id'], unique=False)
    op.create_table('expense_share',
    sa.Column('expense_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['expense_id'], ['expense.id'], name=op.f('fk_expense_share_expense_id_expense')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_expense_share_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expense_share'))
    )
    op.create_index(op.f('ix_expense_share_seq'), 'expense_share', ['seq'], unique=False)
    op.create_index(op.f('ix_expense_share_user_id'), 'expense_share', ['user_id'], unique=False)
    op.create_index('uq_expense_share_live', 'expense_share', ['expense_id', 'user_id'], unique=True, sqlite_where=sa.text('deleted_at IS NULL'))
    # The single global change counter (design D12); never deleted.
    op.execute("INSERT INTO change_counter (id, value) VALUES (1, 0)")


def downgrade() -> None:
    for table in (
        'expense_share', 'expense', 'user_preference', 'shopping_trip', 'payment',
        'item', 'user', 'shopping_list', 'setting', 'change_counter',
    ):
        op.drop_table(table)
