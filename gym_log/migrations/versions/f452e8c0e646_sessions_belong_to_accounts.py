"""sessions and sets belong to an Undercurrent account (user_id)

Existing rows get user_id 'unclaimed'; the owner moves them to her account
with `flask gym claim <email>` after signing up (see gym_log/README.md).

Downgrade deletes the read-only demo's sample rows (user 'demo'; they are
regenerated on demand) and then only works while every remaining row
belongs to one account, since dates would collide otherwise.

Revision ID: f452e8c0e646
Revises: a3930cfc93c3
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "f452e8c0e646"
down_revision = "a3930cfc93c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("gym_sessions", "gym_sets"):
        op.add_column(table, sa.Column("user_id", sa.String(32), nullable=False, server_default="unclaimed"))
    op.drop_constraint("gym_sets_session_date_fkey", "gym_sets", type_="foreignkey")
    op.drop_constraint("gym_sets_pkey", "gym_sets", type_="primary")
    op.drop_constraint("gym_sessions_pkey", "gym_sessions", type_="primary")
    op.create_primary_key("gym_sessions_pkey", "gym_sessions", ["user_id", "session_date"])
    op.create_primary_key("gym_sets_pkey", "gym_sets", ["user_id", "session_date", "exercise_key", "set_no"])
    op.create_foreign_key(
        "gym_sets_session_fkey",
        "gym_sets",
        "gym_sessions",
        ["user_id", "session_date"],
        ["user_id", "session_date"],
        ondelete="CASCADE",
        onupdate="CASCADE",
    )
    for table in ("gym_sessions", "gym_sets"):
        op.alter_column(table, "user_id", server_default=None)


def downgrade() -> None:
    op.execute("DELETE FROM gym_sessions WHERE user_id = 'demo'")  # sets go too (ON DELETE CASCADE)
    op.drop_constraint("gym_sets_session_fkey", "gym_sets", type_="foreignkey")
    op.drop_constraint("gym_sets_pkey", "gym_sets", type_="primary")
    op.drop_constraint("gym_sessions_pkey", "gym_sessions", type_="primary")
    op.create_primary_key("gym_sessions_pkey", "gym_sessions", ["session_date"])
    op.create_primary_key("gym_sets_pkey", "gym_sets", ["session_date", "exercise_key", "set_no"])
    op.create_foreign_key(
        "gym_sets_session_date_fkey", "gym_sets", "gym_sessions", ["session_date"], ["session_date"], ondelete="CASCADE"
    )
    for table in ("gym_sets", "gym_sessions"):
        op.drop_column(table, "user_id")
