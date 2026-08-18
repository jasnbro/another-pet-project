"""JSON API for Mindless Meals.

UI (server-rendered page + vanilla JS) -> this API -> the database.
Kept as one small blueprint rather than split into multiple files —
there are only a handful of routes and splitting further would be
abstraction without payoff for an app this size.
"""
import re

import yaml
from flask import Blueprint, Response, jsonify, request

from db import db
from models import (
    EFFORT_VALUES,
    MEAL_TYPE_VALUES,
    Favorite,
    MealPlan,
    MealPlanItem,
    Recipe,
)

api = Blueprint("api", __name__, url_prefix="/api")


def _slugify_tag(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug


class ValidationError(Exception):
    pass


@api.errorhandler(ValidationError)
def handle_validation_error(err):
    return jsonify({"error": str(err)}), 400


def validate_recipe_payload(payload):
    name = (payload.get("name") or "").strip()
    cuisine = (payload.get("cuisine") or "").strip()
    ingredients = (payload.get("ingredients") or "").strip()
    method = (payload.get("method") or "").strip()
    effort = (payload.get("effort") or "").strip()
    sauce = (payload.get("sauce") or "").strip() or None
    source_url = (payload.get("source_url") or "").strip() or None

    if not name:
        raise ValidationError("Recipe name is required.")
    if not cuisine:
        raise ValidationError("Cuisine is required.")
    if not ingredients:
        raise ValidationError("Ingredients are required.")
    if not method:
        raise ValidationError("Method is required.")
    if effort not in EFFORT_VALUES:
        raise ValidationError(f"Effort must be one of: {', '.join(EFFORT_VALUES)}.")
    if source_url and not re.match(r"^https?://", source_url, re.IGNORECASE):
        raise ValidationError("Recipe link must start with http:// or https://.")

    meal_types = [m for m in (payload.get("meal_types") or []) if m in MEAL_TYPE_VALUES]
    other_raw = payload.get("other_tags") or []
    other_tags = sorted({_slugify_tag(t) for t in other_raw if _slugify_tag(t)})

    return {
        "name": name,
        "cuisine": cuisine,
        "ingredients": ingredients,
        "method": method,
        "effort": effort,
        "sauce": sauce,
        "source_url": source_url,
        "meal_types": meal_types,
        "other_tags": other_tags,
    }


@api.get("/recipes")
def list_recipes():
    recipes = Recipe.query.order_by(Recipe.cuisine, Recipe.name).all()
    return jsonify([r.to_dict() for r in recipes])


@api.post("/recipes")
def create_recipe():
    payload = request.get_json(silent=True) or {}
    fields = validate_recipe_payload(payload)
    recipe = Recipe(source="user", **fields)
    db.session.add(recipe)
    db.session.commit()
    return jsonify(recipe.to_dict()), 201


@api.put("/recipes/<int:recipe_id>")
def update_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    payload = request.get_json(silent=True) or {}
    fields = validate_recipe_payload(payload)
    for key, value in fields.items():
        setattr(recipe, key, value)
    db.session.commit()
    return jsonify(recipe.to_dict())


@api.delete("/recipes/<int:recipe_id>")
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)

    Favorite.query.filter_by(recipe_id=recipe_id).delete()

    affected_plan_ids = {
        item.meal_plan_id for item in MealPlanItem.query.filter_by(recipe_id=recipe_id).all()
    }
    MealPlanItem.query.filter_by(recipe_id=recipe_id).delete()

    db.session.delete(recipe)
    db.session.commit()

    # A meal plan that's now empty because its only recipe(s) were deleted
    # isn't a plan worth keeping around as "the current plan".
    for plan_id in affected_plan_ids:
        plan = db.session.get(MealPlan, plan_id)
        if plan and not plan.items:
            db.session.delete(plan)
    db.session.commit()

    return jsonify({"deleted": True, "id": recipe_id})


@api.get("/recipes/export")
def export_recipes():
    """Every recipe as YAML, in the same shape seed_data/recipes.yaml
    uses — this is both a backup and a re-import path: drop the
    downloaded file in as the seed file and `flask seed` will load
    anything not already present."""
    recipes = Recipe.query.order_by(Recipe.cuisine, Recipe.name).all()
    payload = {
        "recipes": [
            {
                "name": r.name,
                "cuisine": r.cuisine,
                "effort": r.effort,
                "ingredients": r.ingredients,
                "sauce": r.sauce,
                "method": r.method,
                "meal_types": r.meal_types or [],
                "other": r.other_tags or [],
                "source_url": r.source_url,
            }
            for r in recipes
        ]
    }
    body = yaml.dump(payload, sort_keys=False, allow_unicode=True, width=100)
    return Response(
        body,
        mimetype="application/x-yaml",
        headers={"Content-Disposition": "attachment; filename=mindless-meals-export.yaml"},
    )


@api.get("/favorites")
def list_favorites():
    favorite_ids = [f.recipe_id for f in Favorite.query.all()]
    return jsonify({"recipe_ids": favorite_ids})


@api.post("/favorites/<int:recipe_id>")
def add_favorite(recipe_id):
    Recipe.query.get_or_404(recipe_id)
    if not Favorite.query.filter_by(recipe_id=recipe_id).first():
        db.session.add(Favorite(recipe_id=recipe_id))
        db.session.commit()
    return jsonify({"recipe_id": recipe_id, "favorited": True})


@api.delete("/favorites/<int:recipe_id>")
def remove_favorite(recipe_id):
    fav = Favorite.query.filter_by(recipe_id=recipe_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
    return jsonify({"recipe_id": recipe_id, "favorited": False})


@api.get("/meal-plans/current")
def current_meal_plan():
    plan = MealPlan.query.order_by(MealPlan.created_at.desc()).first()
    if not plan:
        return jsonify(None)
    return jsonify(plan.to_dict())


@api.post("/meal-plans")
def save_meal_plan():
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not items:
        raise ValidationError("A meal plan needs at least one recipe.")

    name = (payload.get("name") or "").strip() or "Meal Plan"
    plan = MealPlan(name=name)
    for item in items:
        recipe_id = item.get("recipe_id")
        if not db.session.get(Recipe, recipe_id):
            raise ValidationError(f"Unknown recipe_id: {recipe_id}")
        slot = item.get("slot")
        if slot not in MEAL_TYPE_VALUES:
            slot = None
        plan.items.append(MealPlanItem(recipe_id=recipe_id, slot=slot))

    db.session.add(plan)
    db.session.commit()
    return jsonify(plan.to_dict()), 201
