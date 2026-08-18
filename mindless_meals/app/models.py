"""Data model for Mindless Meals.

Kept deliberately small: recipes, favorites, and saved meal plans are the
only persisted concepts the product needs today. Meal types and "other"
attributes are stored as JSON lists on the recipe rather than as separate
join tables — the vocabulary is small and single-user, so normalizing it
further would be complexity without payoff.
"""
from datetime import datetime, timezone

from db import db

# Effort levels, in order from least to most effort. The color is a CSS
# custom property name (see static/css/mindless-meals.css) rather than a
# literal color, so the palette stays defined in one place.
EFFORT_LEVELS = [
    {"value": "easiest", "label": "Easiest", "color": "--effort-easiest"},
    {"value": "easy", "label": "Easy", "color": "--effort-easy"},
    {"value": "moderate", "label": "Moderate", "color": "--effort-moderate"},
    {"value": "more_effort", "label": "More Effort", "color": "--effort-more"},
]
EFFORT_VALUES = [e["value"] for e in EFFORT_LEVELS]
EFFORT_LABELS = {e["value"]: e["label"] for e in EFFORT_LEVELS}

MEAL_TYPES = [
    {"value": "breakfast", "label": "Breakfast"},
    {"value": "lunch", "label": "Lunch"},
    {"value": "dinner", "label": "Dinner"},
    {"value": "snack", "label": "Snack"},
]
MEAL_TYPE_VALUES = [m["value"] for m in MEAL_TYPES]
MEAL_TYPE_LABELS = {m["value"]: m["label"] for m in MEAL_TYPES}

# Known "Other" attributes, carried over from the original recipe data.
# Add Recipe can introduce new tags beyond this list; these are just the
# ones with a friendlier display label than a straight title-case of the
# raw value.
OTHER_TAG_LABELS = {
    "freezer": "Freezer-Friendly",
    "reheat": "Leftovers-Friendly",
    "high-protein": "High-Protein",
    "fiber": "High-Fiber",
    "bad-week": "Bad-Week Meal",
    "bowl": "Bowl",
    "soup": "Soup",
    "stir-fry": "Stir-Fry",
    "sheet-pan": "Sheet-Pan",
    "emergency": "Emergency Meal",
}


def other_tag_label(tag):
    return OTHER_TAG_LABELS.get(tag, tag.replace("-", " ").replace("_", " ").title())


def _utcnow():
    return datetime.now(timezone.utc)


class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    cuisine = db.Column(db.String(120), nullable=False)
    effort = db.Column(db.String(20), nullable=False, default="easy")
    ingredients = db.Column(db.Text, nullable=False, default="")
    sauce = db.Column(db.Text, nullable=True)
    method = db.Column(db.Text, nullable=False, default="")
    meal_types = db.Column(db.JSON, nullable=False, default=list)
    other_tags = db.Column(db.JSON, nullable=False, default=list)
    # Link to wherever the recipe actually came from — a TikTok/Reels
    # video, a recipe site, etc. Optional; not validated beyond "looks
    # like a URL", since this is a personal reference, not a fetched embed.
    source_url = db.Column(db.String(500), nullable=True)
    # Extension point for future portion guidance (see product spec §13).
    # Deliberately a free-text note rather than structured nutrition data —
    # the product is meant to stay simple portion guidance, not calorie
    # tracking. Left unset for all current recipes.
    portion_note = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(10), nullable=False, default="user")  # "seed" | "user"
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    @property
    def effort_label(self):
        return EFFORT_LABELS.get(self.effort, self.effort)

    @property
    def other_tags_display(self):
        return [other_tag_label(t) for t in (self.other_tags or [])]

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "cuisine": self.cuisine,
            "effort": self.effort,
            "effort_label": self.effort_label,
            "ingredients": self.ingredients,
            "sauce": self.sauce,
            "method": self.method,
            "meal_types": self.meal_types or [],
            "other_tags": self.other_tags or [],
            "other_tags_display": self.other_tags_display,
            "portion_note": self.portion_note,
            "source_url": self.source_url,
        }


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    recipe = db.relationship("Recipe")


class MealPlan(db.Model):
    __tablename__ = "meal_plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default="Meal Plan")
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    items = db.relationship(
        "MealPlanItem", backref="meal_plan", cascade="all, delete-orphan", order_by="MealPlanItem.id"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "items": [item.to_dict() for item in self.items],
        }


class MealPlanItem(db.Model):
    __tablename__ = "meal_plan_items"

    id = db.Column(db.Integer, primary_key=True)
    meal_plan_id = db.Column(db.Integer, db.ForeignKey("meal_plans.id"), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False)
    slot = db.Column(db.String(20), nullable=True)  # breakfast | lunch | dinner | snack | None

    recipe = db.relationship("Recipe")

    def to_dict(self):
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "recipe_name": self.recipe.name if self.recipe else None,
            "slot": self.slot,
        }
