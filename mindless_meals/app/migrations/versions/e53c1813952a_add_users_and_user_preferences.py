"""add users and user preferences

Foundation for "eventually multiple family users" -- not wired into the
app yet (no login flow exists). Deliberately minimal: no auth fields (see
User docstring in models.py), and Favorite/MealPlan are NOT given a
user_id here -- they stay implicitly household-shared until real
authentication exists to attach them to. See
mindless_meals/docs/database.md for the reasoning.

Rollback note: downgrade() drops both tables. Harmless today since nothing
references them yet; if the app starts writing real user data before you
ever need to roll this back, treat that data loss as real and back up
first.

Revision ID: e53c1813952a
Revises: a19f12ebd49b
Create Date: 2026-08-22 22:18:30.743727

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e53c1813952a'
down_revision: Union[str, Sequence[str], None] = 'a19f12ebd49b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EFFORT_VALUES = ["easiest", "easy", "moderate", "more_effort"]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("dietary_restrictions", sa.JSON(), nullable=False),
        sa.Column("default_effort_max", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "default_effort_max IS NULL OR default_effort_max IN ('"
            + "','".join(EFFORT_VALUES)
            + "')",
            name="ck_user_preferences_default_effort_max",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("users")
