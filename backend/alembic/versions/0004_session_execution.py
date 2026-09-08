"""Retain pending operations and active run ownership."""

import sqlalchemy as sa

from alembic import op

revision = "0004_session_execution"
down_revision = "0003_create_session_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("active_run_id", sa.String(36), nullable=True))
    op.add_column("sessions", sa.Column("target_todo_id", sa.String(36), nullable=True))
    op.add_column("sessions", sa.Column("pending_operation", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("pending_operation")
        batch.drop_column("target_todo_id")
        batch.drop_column("active_run_id")
