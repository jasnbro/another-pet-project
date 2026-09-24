"""Recipe (name, cuisine) uniqueness -- promoted from a seed-time dedup
convention into a real database constraint (see models.py)."""
import pytest
from sqlalchemy.exc import IntegrityError

from db import db
from models import Recipe


def _make_recipe(**overrides):
    fields = dict(
        name="Miso Salmon Bowls",
        cuisine="East Asian",
        effort="easy",
        ingredients="Salmon · rice",
        method="Roast salmon → assemble bowls",
    )
    fields.update(overrides)
    return Recipe(**fields)


def test_duplicate_name_and_cuisine_is_rejected_by_the_database(app_instance):
    with app_instance.app_context():
        db.session.add(_make_recipe())
        db.session.commit()

        db.session.add(_make_recipe())
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        assert Recipe.query.count() == 1


def test_same_name_different_cuisine_is_allowed(app_instance):
    with app_instance.app_context():
        db.session.add(_make_recipe())
        db.session.commit()

        db.session.add(_make_recipe(cuisine="Southeast Asian"))
        db.session.commit()

        assert Recipe.query.count() == 2


def test_same_cuisine_different_name_is_allowed(app_instance):
    with app_instance.app_context():
        db.session.add(_make_recipe())
        db.session.commit()

        db.session.add(_make_recipe(name="Gochujang Turkey Bowls"))
        db.session.commit()

        assert Recipe.query.count() == 2
