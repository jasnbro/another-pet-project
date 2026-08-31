"""Expanded export options: scoped recipe export (?ids=) and the current
meal plan export (product spec v1.1 §4)."""
import yaml

RECIPE_A = {
    "name": "Air Fryer Salmon Bites",
    "cuisine": "East Asian",
    "effort": "easiest",
    "ingredients": "Salmon · rice · sesame",
    "method": "Air fry salmon → toss with sauce",
}
RECIPE_B = {
    "name": "Turkey Taco Bowls",
    "cuisine": "Mexican / Tex-Mex",
    "effort": "easy",
    "ingredients": "Ground turkey · rice · black beans",
    "method": "Brown turkey → assemble bowls",
}


def create(client, payload):
    return client.post("/api/recipes", json=payload).get_json()


def test_export_with_no_ids_returns_every_recipe(client):
    create(client, RECIPE_A)
    create(client, RECIPE_B)

    res = client.get("/api/recipes/export")
    parsed = yaml.safe_load(res.get_data(as_text=True))
    assert {r["name"] for r in parsed["recipes"]} == {"Air Fryer Salmon Bites", "Turkey Taco Bowls"}


def test_export_scoped_to_ids_returns_only_those_recipes(client):
    a = create(client, RECIPE_A)
    create(client, RECIPE_B)

    res = client.get("/api/recipes/export?ids=" + str(a["id"]))
    assert res.status_code == 200
    parsed = yaml.safe_load(res.get_data(as_text=True))
    assert len(parsed["recipes"]) == 1
    assert parsed["recipes"][0]["name"] == "Air Fryer Salmon Bites"


def test_export_with_unknown_ids_returns_empty_recipe_list(client):
    create(client, RECIPE_A)

    res = client.get("/api/recipes/export?ids=999999")
    assert res.status_code == 200
    parsed = yaml.safe_load(res.get_data(as_text=True))
    assert parsed["recipes"] == []


def test_export_rejects_malformed_ids(client):
    res = client.get("/api/recipes/export?ids=abc")
    assert res.status_code == 400


def test_meal_plan_export_with_no_saved_plan_is_rejected(client):
    res = client.get("/api/meal-plans/current/export")
    assert res.status_code == 400


def test_meal_plan_export_groups_by_slot(client):
    a = create(client, RECIPE_A)
    b = create(client, RECIPE_B)
    client.post(
        "/api/meal-plans",
        json={
            "name": "This Week",
            "items": [
                {"recipe_id": a["id"], "slot": "lunch"},
                {"recipe_id": b["id"], "slot": "dinner"},
            ],
        },
    )

    res = client.get("/api/meal-plans/current/export")
    assert res.status_code == 200
    assert "text/plain" in res.content_type
    body = res.get_data(as_text=True)
    assert "This Week" in body
    assert "Lunch:" in body
    assert "  - Air Fryer Salmon Bites" in body
    assert "Dinner:" in body
    assert "  - Turkey Taco Bowls" in body
    # Lunch section must come before Dinner (MEAL_TYPE_VALUES order)
    assert body.index("Lunch:") < body.index("Dinner:")


def test_meal_plan_export_handles_unslotted_items(client):
    a = create(client, RECIPE_A)
    client.post("/api/meal-plans", json={"items": [{"recipe_id": a["id"], "slot": None}]})

    res = client.get("/api/meal-plans/current/export")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Other:" in body
    assert "  - Air Fryer Salmon Bites" in body
