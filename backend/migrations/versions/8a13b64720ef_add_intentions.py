"""Add the temporary intentions store and task-source scheduling metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from underway.models.types import MySQLUUID

revision: str = "8a13b64720ef"
down_revision: str | Sequence[str] | None = "767105043a33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intentions",
        sa.Column("user_id", MySQLUUID(), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("last_warnings", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_published", sa.DateTime(), nullable=True),
    )
    op.add_column("tasks", sa.Column("deadline", sa.DateTime(), nullable=True))
    op.add_column("tasks", sa.Column("estimated_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "estimated_minutes")
    op.drop_column("tasks", "deadline")
    op.drop_table("intentions")
