"""add endpoint routing metadata and task affinity

Revision ID: 73f51ca48d20
Revises: 078d93562b70
Create Date: 2026-10-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "73f51ca48d20"
down_revision: str | Sequence[str] | None = "078d93562b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proxy_requests",
        sa.Column("method", sa.String(length=10), server_default="POST", nullable=False),
    )
    op.add_column(
        "proxy_requests",
        sa.Column("endpoint", sa.String(length=100), server_default="search", nullable=False),
    )
    op.add_column(
        "proxy_requests",
        sa.Column("path", sa.String(length=500), server_default="/search", nullable=False),
    )
    op.add_column("tavily_keys", sa.Column("rate_limit_cooldowns", sa.JSON(), nullable=True))
    op.create_table(
        "task_affinities",
        sa.Column("pool_id", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=200), nullable=False),
        sa.Column("key_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["key_id"], ["tavily_keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pool_id"], ["pools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pool_id", "resource_id"),
    )
    op.create_index("ix_task_affinities_key", "task_affinities", ["key_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_affinities_key", table_name="task_affinities")
    op.drop_table("task_affinities")
    op.drop_column("tavily_keys", "rate_limit_cooldowns")
    op.drop_column("proxy_requests", "path")
    op.drop_column("proxy_requests", "endpoint")
    op.drop_column("proxy_requests", "method")
