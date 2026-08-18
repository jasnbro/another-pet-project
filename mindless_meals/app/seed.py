"""Loads seed_data/recipes.yaml into the database.

The YAML file is the one-time export of the original meal-atlas.html
prototype's recipe content (see mindless_meals/README.md). It is treated
as import/seed data only — recipes added afterwards through the app live
solely in the database, per the "static files as seed data, real state in
the DB" split described in the product spec.

Idempotent by recipe name + cuisine: re-running the seed does not create
duplicates, so it's safe to call on every app startup when the table is
new/empty.
"""
import os

import yaml

from db import db
from models import Recipe

SEED_FILE = os.path.join(os.path.dirname(__file__), "seed_data", "recipes.yaml")


def seed_recipes():
    with open(SEED_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    added = 0
    for entry in data.get("recipes", []):
        exists = Recipe.query.filter_by(name=entry["name"], cuisine=entry["cuisine"]).first()
        if exists:
            continue
        recipe = Recipe(
            name=entry["name"],
            cuisine=entry["cuisine"],
            effort=entry.get("effort", "easy"),
            ingredients=entry.get("ingredients", ""),
            sauce=entry.get("sauce"),
            method=entry.get("method", ""),
            meal_types=entry.get("meal_types", []),
            other_tags=entry.get("other", []),
            source_url=entry.get("source_url"),
            source="seed",
        )
        db.session.add(recipe)
        added += 1

    db.session.commit()
    return added
