"""gym_sessions and gym_sets

Revision ID: 0001
Revises:
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gym_sessions",
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("day_code", sa.Text(), nullable=False),
        sa.Column("finished", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("warmup_done", postgresql.ARRAY(sa.Boolean()), server_default="{}", nullable=False),
        sa.Column("rope_rounds", postgresql.ARRAY(sa.Boolean()), server_default="{}", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("session_date"),
    )
    op.create_table(
        "gym_sets",
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("exercise_key", sa.Text(), nullable=False),
        sa.Column("set_no", sa.SmallInteger(), nullable=False),
        sa.Column("weight", sa.Numeric(5, 1), nullable=True),
        sa.Column("band", sa.Text(), nullable=True),
        sa.Column("reps", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["session_date"], ["gym_sessions.session_date"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_date", "exercise_key", "set_no"),
    )


def downgrade() -> None:
    op.drop_table("gym_sets")
    op.drop_table("gym_sessions")
