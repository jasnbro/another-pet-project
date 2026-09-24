"""baseline schema

Captures the schema Mindless Meals already runs today (previously created
ad hoc by db.create_all(), with no migration history) as the first
Alembic revision: recipes, favorites, and meal plans. This is the starting
point every other migration builds on.

Rollback note: downgrade() drops these tables entirely -- there is no
"before" state to return to, since this is the first revision. Don't run
it against a database with real recipes/favorites/meal plans you want to
keep; back up first (see mindless_meals/docs/database.md#backups).

Revision ID: 200140706353
Revises:
Create Date: 2026-08-22 22:18:29.349752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '200140706353'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("cuisine", sa.String(length=120), nullable=False),
        sa.Column("effort", sa.String(length=20), nullable=False),
        sa.Column("ingredients", sa.Text(), nullable=False),
        sa.Column("sauce", sa.Text(), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("meal_types", sa.JSON(), nullable=False),
        sa.Column("other_tags", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("portion_note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_recipes_cuisine", "recipes", ["cuisine"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recipe_id",
            sa.Integer(),
            sa.ForeignKey("recipes.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "meal_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_meal_plans_created_at", "meal_plans", ["created_at"])

    op.create_table(
        "meal_plan_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "meal_plan_id", sa.Integer(), sa.ForeignKey("meal_plans.id"), nullable=False
        ),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("slot", sa.String(length=20), nullable=True),
    )
    op.create_index("ix_meal_plan_items_meal_plan_id", "meal_plan_items", ["meal_plan_id"])


def downgrade() -> None:
    op.drop_table("meal_plan_items")
    op.drop_table("meal_plans")
    op.drop_table("favorites")
    op.drop_table("recipes")
