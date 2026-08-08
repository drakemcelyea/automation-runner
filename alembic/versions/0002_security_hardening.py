"""Add authentication lockout and persistent login throttling.

Revision ID: 0002_security_hardening
Revises: 0001_current_schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0002_security_hardening"
down_revision: Union[str, None] = "0001_current_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "users" in tables:
        columns = _column_names("users")
        if "failed_login_attempts" not in columns:
            op.add_column(
                "users",
                sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
            )
        columns = _column_names("users")
        if "locked_until" not in columns:
            op.add_column(
                "users",
                sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
            )

    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "login_throttles" not in tables:
        op.create_table(
            "login_throttles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("key_hash", sa.String(length=64), nullable=False),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key_hash"),
        )
        op.create_index(
            "ix_login_throttles_key_hash",
            "login_throttles",
            ["key_hash"],
            unique=True,
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "login_throttles" in tables:
        indexes = {idx["name"] for idx in inspector.get_indexes("login_throttles") if idx.get("name")}
        if "ix_login_throttles_key_hash" in indexes:
            op.drop_index("ix_login_throttles_key_hash", table_name="login_throttles")
        op.drop_table("login_throttles")

    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "users" in tables:
        columns = _column_names("users")
        with op.batch_alter_table("users") as batch_op:
            if "locked_until" in columns:
                batch_op.drop_column("locked_until")
            if "failed_login_attempts" in columns:
                batch_op.drop_column("failed_login_attempts")
