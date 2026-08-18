"""Seed loading: the YAML seed populates the DB once, and re-running it
is a no-op rather than creating duplicates (product spec §14)."""
import yaml

from app import create_app
from db import db
from models import Recipe
from seed import SEED_FILE, seed_recipes


def test_seed_yaml_is_well_formed():
    with open(SEED_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    recipes = data["recipes"]
    assert len(recipes) > 0
    for entry in recipes:
        assert entry["name"]
        assert entry["cuisine"]
        assert entry["ingredients"]
        assert entry["method"]


def test_seeding_twice_does_not_duplicate():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://", "SEED_ON_START": False, "TESTING": True})
    with app.app_context():
        first_added = seed_recipes()
        count_after_first = Recipe.query.count()
        assert first_added == count_after_first
        assert first_added > 0

        second_added = seed_recipes()
        assert second_added == 0
        assert Recipe.query.count() == count_after_first

        db.session.remove()
        db.drop_all()
