"""adopt_existing_atlas_schema_drift

Revision ID: f142ebece5e8
Revises: 36f0f5d50122
Create Date: 2026-10-09

One-time adoption for the real Atlas deployment specifically: two
prior deploys ran app.py's old, unconditional db.create_all() against
this database before Alembic tracking existed, which silently created
every table in this migration chain but could not alter the
PRE-EXISTING recipes/meal_plans/meal_plan_items tables to add the
UNIQUE(name, cuisine) constraint or the three indexes below (create_all()
never alters an existing table). Atlas was then stamped at head
(these statements were the only actual schema difference from head --
verified via alembic revision --autogenerate producing an empty diff
immediately after this migration applied).

Written defensively (IF NOT EXISTS / existence-checked DO blocks) so
it is also a safe no-op on a fresh deploy, where the earlier
'add unique constraint on recipe name and cuisine' migration already
created these exact objects in the normal course of the chain.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f142ebece5e8'
down_revision: Union[str, Sequence[str], None] = '36f0f5d50122'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_recipes_name_cuisine'
            ) THEN
                ALTER TABLE recipes ADD CONSTRAINT uq_recipes_name_cuisine UNIQUE (name, cuisine);
            END IF;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_recipes_cuisine ON recipes (cuisine)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_meal_plans_created_at ON meal_plans (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_meal_plan_items_meal_plan_id ON meal_plan_items (meal_plan_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_meal_plan_items_meal_plan_id")
    op.execute("DROP INDEX IF EXISTS ix_meal_plans_created_at")
    op.execute("DROP INDEX IF EXISTS ix_recipes_cuisine")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_recipes_name_cuisine'
            ) THEN
                ALTER TABLE recipes DROP CONSTRAINT uq_recipes_name_cuisine;
            END IF;
        END $$;
        """
    )
