"""add grocery lists

Adds shopping-list support: a GroceryList optionally generated from a
MealPlan, holding items that are either a catalog Ingredient (derived from
a recipe) or a freeform custom_text entry (e.g. "paper towels") -- never
neither, enforced by a CHECK constraint. Not wired into the app yet.

Rollback note: downgrade() drops both tables and any lists/items in them.
Recipes, meal plans, and ingredients are untouched either direction.

Revision ID: 36f0f5d50122
Revises: e53c1813952a
Create Date: 2026-08-22 22:18:31.085032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36f0f5d50122'
down_revision: Union[str, Sequence[str], None] = 'e53c1813952a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grocery_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "meal_plan_id",
            sa.Integer(),
            sa.ForeignKey("meal_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "grocery_list_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "grocery_list_id",
            sa.Integer(),
            sa.ForeignKey("grocery_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("custom_text", sa.String(length=200), nullable=True),
        sa.Column("is_checked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "ingredient_id IS NOT NULL OR custom_text IS NOT NULL",
            name="ck_grocery_list_items_has_content",
        ),
    )
    op.create_index("ix_grocery_list_items_grocery_list_id", "grocery_list_items", ["grocery_list_id"])


def downgrade() -> None:
    op.drop_table("grocery_list_items")
    op.drop_table("grocery_lists")
