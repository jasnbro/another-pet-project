"""Export Recipes: a backup that doubles as a re-import (seed) file."""
import yaml

RECIPE_PAYLOAD = {
    "name": "Air Fryer Salmon Bites",
    "cuisine": "East Asian",
    "effort": "easiest",
    "ingredients": "Salmon · rice · sesame",
    "sauce": "Soy · sesame oil",
    "method": "Air fry salmon → toss with sauce",
    "meal_types": ["dinner"],
    "other_tags": ["high-protein"],
    "source_url": "https://www.tiktok.com/@chef/video/999",
}


def test_export_is_valid_yaml_matching_seed_shape(client):
    client.post("/api/recipes", json=RECIPE_PAYLOAD)

    res = client.get("/api/recipes/export")
    assert res.status_code == 200
    assert "yaml" in res.content_type

    parsed = yaml.safe_load(res.get_data(as_text=True))
    assert "recipes" in parsed
    assert len(parsed["recipes"]) == 1

    entry = parsed["recipes"][0]
    assert entry["name"] == "Air Fryer Salmon Bites"
    assert entry["cuisine"] == "East Asian"
    assert entry["sauce"] == "Soy · sesame oil"
    assert entry["meal_types"] == ["dinner"]
    # "other", not "other_tags" -- must match the seed loader's key exactly
    assert entry["other"] == ["high-protein"]
    assert entry["source_url"] == "https://www.tiktok.com/@chef/video/999"


def test_export_is_reimportable_via_the_seed_loader(app_instance, client):
    from db import db
    from models import Recipe
    from seed import seed_recipes

    client.post("/api/recipes", json=RECIPE_PAYLOAD)
    exported_yaml = client.get("/api/recipes/export").get_data(as_text=True)

    with app_instance.app_context():
        # wipe and reload purely from the exported file, proving round-trip fidelity
        Recipe.query.delete()
        db.session.commit()

        import seed as seed_module

        original_seed_file = seed_module.SEED_FILE
        tmp_path = "/tmp/mindless_meals_export_roundtrip.yaml"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(exported_yaml)
        seed_module.SEED_FILE = tmp_path
        try:
            added = seed_recipes()
        finally:
            seed_module.SEED_FILE = original_seed_file

        assert added == 1
        restored = Recipe.query.first()
        assert restored.name == "Air Fryer Salmon Bites"
        assert restored.source_url == "https://www.tiktok.com/@chef/video/999"
