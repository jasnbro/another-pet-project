"""Populates ingredients / recipe_ingredients from Recipe rows already in
the database.

Reads Recipe.ingredients and Recipe.sauce -- the same free-text fields the
app has always used -- rather than seed_data/recipes.yaml directly, so it
covers both the 48 seeded recipes and anything a user later adds or edits
through the app (Add/Edit Recipe write those same two columns). Neither
column is modified: this only builds an additional, derived view on top of
them.

Idempotent by design:
- Ingredient rows are looked up/created by name (unique), never duplicated.
- RecipeIngredient links are looked up by (recipe_id, ingredient_id) before
  inserting, so re-running after adding new recipes only adds what's
  missing.
- Nothing is ever deleted here. If a recipe's ingredients text changes
  (via Edit) such that it no longer lists something it used to, the old
  link is left in place -- this importer only adds, it doesn't reconcile
  removals. Re-running after bulk edits may leave stale links; there's no
  data-loss risk in that, just possible staleness, and it's cheap to spot
  (a recipe_ingredients row whose ingredient no longer appears in the
  recipe's text) if that starts to matter.

Ingredient tokens are matched case-insensitively against the curated
catalog in seed_data/ingredients.yaml. An ingredient name/phrase not found
there (e.g. a new recipe using an ingredient the catalog has never seen)
is still linked -- created as a new Ingredient row with group and
nutrition_type left NULL -- rather than silently dropped or rejected. Run
this command's report tells you which ones need manual classification
(add them to ingredients.yaml with a group/nutrition_type and re-run to
pick up the correction).

Two small text-normalization rules, both reviewed by hand against every
recipe in the current seed data (not applied blindly):

1. A literal "or "/"and " prefix left over from prose is stripped (one
   sauce field reads "Buffalo · teriyaki · or gochujang yogurt" -- the
   third item's real name is "gochujang yogurt").
2. A short list of known "either works" source phrases (e.g. "Ground
   turkey/beef") are merged into one canonical ingredient (e.g. "Ground
   Meat (Any)") rather than kept as separate, oddly-named entries. This is
   an editorial call, not a general parsing rule -- COMPOUND_MERGES below
   is the complete, exhaustive list of phrases it applies to; anything not
   listed there is kept exactly as written (e.g. "Salt & pepper" would
   stay one ingredient, not split into "Salt" and "pepper").

Two sauce-field placeholder values ("—" and "Any sauce in fridge", used on
a few "emergency meal" recipes to mean "whatever you have") are skipped
entirely rather than becoming ingredient rows -- they're not real
ingredients. Recipe.sauce itself is untouched, so this text isn't lost,
just not promoted into the catalog.

Run via: flask import-ingredients
"""
import os
import re

import yaml

from db import db
from models import Ingredient, Recipe, RecipeIngredient

CATALOG_FILE = os.path.join(os.path.dirname(__file__), "seed_data", "ingredients.yaml")

PLACEHOLDERS = {"—", "any sauce in fridge"}

# Literal source phrase (lowercase) -> canonical ingredient name. See the
# module docstring above -- this is a fixed, hand-reviewed list, not a
# general "split on / or 'or'" rule.
COMPOUND_MERGES = {
    "ground turkey/beef": "Ground Meat (Any)",
    "ground turkey/chicken": "Ground Meat (Any)",
    "chicken legs/thighs": "Chicken (Legs or Thighs)",
    "broccoli/cabbage": "Broccoli or Cabbage",
    "collards/spinach": "Collard Greens or Spinach",
    "kale/spinach": "Kale or Spinach",
    "tofu/chicken": "Tofu or Chicken",
    "chicken thighs or tofu": "Tofu or Chicken",
}


def _normalize(raw):
    s = raw.strip()
    return re.sub(r"^(or|and)\s+", "", s, flags=re.IGNORECASE)


def _load_catalog():
    """Returns {canonical_name: catalog_entry_dict, lowercase_name: canonical_name}."""
    with open(CATALOG_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    by_name = {}
    name_lookup = {}
    for entry in data.get("ingredients", []):
        by_name[entry["name"]] = entry
        name_lookup[entry["name"].lower()] = entry["name"]
    return by_name, name_lookup


def _resolve_canonical_name(token, name_lookup, unmapped):
    low = token.lower()
    if low in COMPOUND_MERGES:
        return COMPOUND_MERGES[low]
    if low in name_lookup:
        return name_lookup[low]
    unmapped.add(token)
    return token.title()


def import_ingredients():
    """Idempotent. Returns a report dict summarizing what happened, for
    `flask import-ingredients` to print."""
    catalog_by_name, name_lookup = _load_catalog()
    ingredient_cache = {i.name: i for i in Ingredient.query.all()}

    report = {
        "recipes_processed": 0,
        "links_created": 0,
        "ingredients_created": 0,
        "skipped_placeholders": set(),
        "unmapped_tokens": set(),
    }

    for recipe in Recipe.query.order_by(Recipe.id).all():
        report["recipes_processed"] += 1

        tokens = []
        for field in ("ingredients", "sauce"):
            raw = getattr(recipe, field) or ""
            for part in raw.split("·"):  # '·'
                part = _normalize(part)
                if not part:
                    continue
                if part.lower() in PLACEHOLDERS:
                    report["skipped_placeholders"].add(part)
                    continue
                tokens.append(part)

        for token in tokens:
            canonical_name = _resolve_canonical_name(token, name_lookup, report["unmapped_tokens"])

            ingredient = ingredient_cache.get(canonical_name)
            if ingredient is None:
                entry = catalog_by_name.get(canonical_name)
                ingredient = Ingredient(
                    name=canonical_name,
                    group=(entry or {}).get("group"),
                    nutrition_type=(entry or {}).get("nutrition_type"),
                    aliases=(entry or {}).get("aliases") or [],
                )
                db.session.add(ingredient)
                db.session.flush()  # assign ingredient.id without committing yet
                ingredient_cache[canonical_name] = ingredient
                report["ingredients_created"] += 1

            link_exists = RecipeIngredient.query.filter_by(
                recipe_id=recipe.id, ingredient_id=ingredient.id
            ).first()
            if link_exists is None:
                db.session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=ingredient.id))
                report["links_created"] += 1

    db.session.commit()
    return report
