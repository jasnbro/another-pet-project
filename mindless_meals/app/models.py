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
    "reheat": "Leftover-Friendly",
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


# Fixed vocabularies for the ingredient catalog (see Ingredient below),
# kept as Python constants rather than lookup tables -- same reasoning as
# EFFORT_LEVELS/MEAL_TYPES above: small, closed-ish, single-household. Both
# are nullable on Ingredient: a newly-imported ingredient the curated
# seed_data/ingredients.yaml doesn't yet cover is added unclassified rather
# than guessed at or rejected (see import_ingredients.py).
INGREDIENT_GROUPS = [
    "meat", "seafood", "dairy", "egg", "vegetable", "fruit",
    "grain", "legume", "pantry", "other",
]
NUTRITION_TYPES = ["protein", "carb", "fat", "fiber", "other"]


class Recipe(db.Model):
    __tablename__ = "recipes"
    __table_args__ = (
        db.UniqueConstraint("name", "cuisine", name="uq_recipes_name_cuisine"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # Indexed: the home page groups/orders every recipe by cuisine on
    # every load (see app.py's home()).
    cuisine = db.Column(db.String(120), nullable=False, index=True)
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


class Ingredient(db.Model):
    """A catalog entry for one raw ingredient (e.g. "Carrots") -- no
    quantity or unit, just the fact that a recipe uses it. See
    import_ingredients.py and seed_data/ingredients.yaml for how
    this is populated from the existing free-text Recipe.ingredients/sauce
    fields, which remain the source of truth and are not modified by this.

    A handful of catalog entries stand in for a choice the original recipe
    text offered between a few specific items (e.g. "ground turkey/beef" ->
    "Ground Meat (Any)") -- `aliases` lists those specific items so a
    search for e.g. "beef" still finds the recipe. Stored as JSON (not a
    Postgres ARRAY) to match the existing meal_types/other_tags convention
    on Recipe and keep the SQLite dev/test path working unchanged.
    """

    __tablename__ = "ingredients"
    __table_args__ = (
        db.CheckConstraint(
            "\"group\" IS NULL OR \"group\" IN ('" + "','".join(INGREDIENT_GROUPS) + "')",
            name="ck_ingredients_group",
        ),
        db.CheckConstraint(
            "nutrition_type IS NULL OR nutrition_type IN ('" + "','".join(NUTRITION_TYPES) + "')",
            name="ck_ingredients_nutrition_type",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    # Column is named "group" in the DB; Python attribute avoids shadowing
    # the builtin. `group` is a reserved-ish word in some SQL dialects
    # hence the quoting in the CHECK constraint above.
    group = db.Column("group", db.String(20), nullable=True)
    nutrition_type = db.Column(db.String(20), nullable=True)
    aliases = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "group": self.group,
            "nutrition_type": self.nutrition_type,
            "aliases": self.aliases or [],
        }


class RecipeIngredient(db.Model):
    """Join table linking a Recipe to an Ingredient it uses. No quantity or
    unit by design -- see mindless_meals/docs/database.md for why."""

    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        db.UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredients_pair"),
    )

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(
        db.Integer, db.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id = db.Column(
        db.Integer, db.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    recipe = db.relationship("Recipe", backref=db.backref("recipe_ingredients", cascade="all, delete-orphan"))
    ingredient = db.relationship("Ingredient")


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
    # Indexed: current_meal_plan() (api.py) always orders by created_at
    # desc to find "the most recent plan".
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

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
    meal_plan_id = db.Column(
        db.Integer, db.ForeignKey("meal_plans.id"), nullable=False, index=True
    )
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


# --- Forward-looking tables (not yet wired into api.py/the UI) -----------
#
# Mindless Meals is single-user today with no authentication, so nothing
# above (Favorite, MealPlan) carries a user_id -- retrofitting that now
# would mean either a nullable FK with an awkward NULL-uniqueness story or
# inventing an auth system this project doesn't have yet. Instead, User /
# UserPreference / GroceryList are added additively as the foundation the
# product spec's "eventually multiple family users" and "grocery lists"
# goals will build on, once there's a real login flow to attach them to.


class User(db.Model):
    """Deliberately minimal: a name to attach preferences/lists to later.
    No password/auth fields -- authentication is out of scope for this
    schema and shouldn't be speculatively designed here."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)


class UserPreference(db.Model):
    """One row per user. Kept to a few concrete fields rather than an
    open-ended JSON blob of "preferences" -- extend with real columns (or a
    new table, e.g. per-ingredient dislikes) as actual features need them."""

    __tablename__ = "user_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # e.g. ["vegetarian", "dairy-free"] -- open-ended like Recipe.other_tags,
    # so not worth a fixed vocabulary/lookup table.
    dietary_restrictions = db.Column(db.JSON, nullable=False, default=list)
    # "don't suggest anything harder than this" -- reuses the effort scale
    # recipes already have.
    default_effort_max = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    user = db.relationship("User", backref=db.backref("preferences", uselist=False, cascade="all, delete-orphan"))

    __table_args__ = (
        db.CheckConstraint(
            "default_effort_max IS NULL OR default_effort_max IN ('" + "','".join(EFFORT_VALUES) + "')",
            name="ck_user_preferences_default_effort_max",
        ),
    )


class GroceryList(db.Model):
    """A shopping list, optionally generated from a MealPlan (via its
    recipes' recipe_ingredients) and/or built up with freeform items."""

    __tablename__ = "grocery_lists"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default="Grocery List")
    meal_plan_id = db.Column(
        db.Integer, db.ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    meal_plan = db.relationship("MealPlan")
    created_by = db.relationship("User")
    items = db.relationship(
        "GroceryListItem", backref="grocery_list", cascade="all, delete-orphan", order_by="GroceryListItem.id"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "meal_plan_id": self.meal_plan_id,
            "created_at": self.created_at.isoformat(),
            "items": [item.to_dict() for item in self.items],
        }


class GroceryListItem(db.Model):
    """Either tied to a catalog Ingredient (derived from a recipe) or a
    freeform custom_text item (e.g. "paper towels") -- never neither,
    enforced by the CHECK constraint below."""

    __tablename__ = "grocery_list_items"
    __table_args__ = (
        db.CheckConstraint(
            "ingredient_id IS NOT NULL OR custom_text IS NOT NULL",
            name="ck_grocery_list_items_has_content",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    grocery_list_id = db.Column(
        db.Integer, db.ForeignKey("grocery_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id = db.Column(
        db.Integer, db.ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    custom_text = db.Column(db.String(200), nullable=True)
    is_checked = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    ingredient = db.relationship("Ingredient")

    def to_dict(self):
        return {
            "id": self.id,
            "ingredient_id": self.ingredient_id,
            "label": self.ingredient.name if self.ingredient else self.custom_text,
            "is_checked": self.is_checked,
        }
