"""Baseline current Automation Runner schema.

This migration is intentionally adoption-safe. If an existing deployment already
has the users and/or audit_logs tables, those tables are left intact and Alembic
simply begins tracking the schema from this revision.

Revision ID: 0001_current_schema
Revises: None
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0001_current_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {idx["name"] for idx in inspector.get_indexes(table_name) if idx.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Refresh inspector after any table creation.
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("actor_username", sa.String(length=64), nullable=True),
            sa.Column("action", sa.String(length=96), nullable=False),
            sa.Column("outcome", sa.String(length=16), nullable=False),
            sa.Column("resource_type", sa.String(length=64), nullable=True),
            sa.Column("resource_id", sa.String(length=128), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        for name, column in (
            ("ix_audit_logs_created_at", "created_at"),
            ("ix_audit_logs_actor_user_id", "actor_user_id"),
            ("ix_audit_logs_actor_username", "actor_username"),
            ("ix_audit_logs_action", "action"),
            ("ix_audit_logs_outcome", "outcome"),
            ("ix_audit_logs_resource_type", "resource_type"),
        ):
            op.create_index(name, "audit_logs", [column], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "audit_logs" in tables:
        for index_name in sorted(_index_names("audit_logs"), reverse=True):
            op.drop_index(index_name, table_name="audit_logs")
        op.drop_table("audit_logs")

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" in tables:
        for index_name in sorted(_index_names("users"), reverse=True):
            op.drop_index(index_name, table_name="users")
        op.drop_table("users")
