"""add unique constraint on recipe name and cuisine

Promotes the app's existing dedup rule (seed.py's seed_recipes() already
treats name+cuisine as the identity of a recipe when deciding whether to
insert it) into a real database constraint, so duplicate recipes can't be
created any other way either.

Behavior change to be aware of: creating or editing a recipe to a
name+cuisine that already exists now fails at the database level (a
constraint violation) instead of silently succeeding. mindless_meals'
api.py does not currently translate that into a friendly validation
message -- see mindless_meals/docs/database.md for this known gap.

Rollback note: downgrade() only drops the constraint -- no data is
affected either direction. Forward migration will fail if the database
already contains duplicate (name, cuisine) pairs; resolve those manually
(e.g. via the app's Export Recipes / Edit) before upgrading.

Revision ID: a19f12ebd49b
Revises: fca1abd0627d
Create Date: 2026-08-22 22:18:30.381165

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a19f12ebd49b'
down_revision: Union[str, Sequence[str], None] = 'fca1abd0627d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_recipes_name_cuisine", "recipes", ["name", "cuisine"])


def downgrade() -> None:
    op.drop_constraint("uq_recipes_name_cuisine", "recipes", type_="unique")
