"""Create sessions, messages and tool_events without coupling history to todos."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_create_session_tables"
down_revision: str | None = "0002_create_todo_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'running', 'waiting_input', 'completed', 'failed', 'cancelled')",
            name="ck_sessions_status",
        ),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        sa.CheckConstraint("position >= 0", name="ck_messages_position"),
        sa.UniqueConstraint("session_id", "position", name="uq_messages_session_position"),
    )
    op.create_table(
        "tool_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("call_id", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "event_type IN ('started', 'completed', 'failed', 'cancelled')",
            name="ck_tool_events_type",
        ),
        sa.CheckConstraint("position >= 0", name="ck_tool_events_position"),
        sa.UniqueConstraint("session_id", "position", name="uq_tool_events_session_position"),
    )


def downgrade() -> None:
    op.drop_table("tool_events")
    op.drop_table("messages")
    op.drop_table("sessions")
