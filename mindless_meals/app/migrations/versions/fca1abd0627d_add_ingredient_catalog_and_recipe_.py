"""add ingredient catalog and recipe ingredients

Adds the normalized ingredient list: `ingredients` (a catalog of raw items
-- no quantity/unit, see mindless_meals/docs/database.md) and
`recipe_ingredients` (which recipes use which ingredients). Populate these
from the existing recipes via `flask import-ingredients`
(mindless_meals/app/import_ingredients.py) -- this migration
only creates the empty tables.

Does not touch Recipe.ingredients/Recipe.sauce -- those free-text columns
remain the source of truth for what a recipe displays; this is an
additive, derived view for future search/grocery-list features.

Rollback note: downgrade() drops both tables and everything in them. Any
ingredient links created by the importer are lost; the source recipe text
they were derived from is untouched and the importer can be re-run after a
later re-upgrade.

Revision ID: fca1abd0627d
Revises: 200140706353
Create Date: 2026-08-22 22:18:29.825820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fca1abd0627d'
down_revision: Union[str, Sequence[str], None] = '200140706353'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Kept identical to models.INGREDIENT_GROUPS / NUTRITION_TYPES so the CHECK
# constraints below match exactly what SQLAlchemy would generate. If those
# vocabularies ever change, add a new migration with an ALTER of the CHECK
# constraint rather than editing this file.
INGREDIENT_GROUPS = [
    "meat", "seafood", "dairy", "egg", "vegetable", "fruit",
    "grain", "legume", "pantry", "other",
]
NUTRITION_TYPES = ["protein", "carb", "fat", "fiber", "other"]


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("group", sa.String(length=20), nullable=True),
        sa.Column("nutrition_type", sa.String(length=20), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "\"group\" IS NULL OR \"group\" IN ('" + "','".join(INGREDIENT_GROUPS) + "')",
            name="ck_ingredients_group",
        ),
        sa.CheckConstraint(
            "nutrition_type IS NULL OR nutrition_type IN ('" + "','".join(NUTRITION_TYPES) + "')",
            name="ck_ingredients_nutrition_type",
        ),
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recipe_id",
            sa.Integer(),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredients_pair"),
    )
    op.create_index("ix_recipe_ingredients_recipe_id", "recipe_ingredients", ["recipe_id"])
    op.create_index("ix_recipe_ingredients_ingredient_id", "recipe_ingredients", ["ingredient_id"])


def downgrade() -> None:
    op.drop_table("recipe_ingredients")
    op.drop_table("ingredients")
