"""Create todos and todo_items tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_create_todo_tables"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "todos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="ck_todos_position"),
        sa.CheckConstraint("priority IN (0, 1)", name="ck_todos_priority"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "todo_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("todo_id", sa.String(length=36), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("completed IN (0, 1)", name="ck_todo_items_completed"),
        sa.CheckConstraint("position >= 0", name="ck_todo_items_position"),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_todo_items_todo_id", "todo_items", ["todo_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_todo_items_todo_id", table_name="todo_items")
    op.drop_table("todo_items")
    op.drop_table("todos")
