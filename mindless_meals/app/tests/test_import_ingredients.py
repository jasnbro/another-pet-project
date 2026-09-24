"""`flask import-ingredients`: populating the ingredient catalog from
existing Recipe rows (see import_ingredients.py)."""
from import_ingredients import import_ingredients
from models import Ingredient, RecipeIngredient


def create_recipe(client, **overrides):
    payload = dict(
        name="Test Recipe",
        cuisine="Test Cuisine",
        effort="easy",
        ingredients="Salmon · rice",
        method="Cook everything",
    )
    payload.update(overrides)
    return client.post("/api/recipes", json=payload).get_json()["id"]


def test_import_creates_ingredients_and_links(app_instance, client):
    create_recipe(client, ingredients="Salmon · rice · cucumber", sauce="Soy · ginger")

    with app_instance.app_context():
        report = import_ingredients()

        assert report["recipes_processed"] == 1
        assert report["ingredients_created"] == 5
        assert report["links_created"] == 5
        assert Ingredient.query.count() == 5
        assert RecipeIngredient.query.count() == 5


def test_import_is_idempotent(app_instance, client):
    create_recipe(client, ingredients="Salmon · rice", sauce=None)

    with app_instance.app_context():
        first = import_ingredients()
        second = import_ingredients()

    assert first["ingredients_created"] == 2
    assert first["links_created"] == 2
    assert second["ingredients_created"] == 0
    assert second["links_created"] == 0


def test_compound_merge_maps_to_one_canonical_ingredient(app_instance, client):
    create_recipe(client, ingredients="Ground turkey/beef · cabbage", sauce=None)

    with app_instance.app_context():
        import_ingredients()
        names = {i.name for i in Ingredient.query.all()}

    assert "Ground Meat (Any)" in names
    assert "Ground turkey/beef" not in names


def test_placeholder_sauce_values_are_skipped_not_imported(app_instance, client):
    create_recipe(client, ingredients="Rice", sauce="—")
    create_recipe(client, name="Other Recipe", ingredients="Beans", sauce="Any sauce in fridge")

    with app_instance.app_context():
        report = import_ingredients()
        names = {i.name for i in Ingredient.query.all()}

    assert report["skipped_placeholders"] == {"—", "Any sauce in fridge"}
    assert "—" not in names
    assert "Any sauce in fridge" not in names
