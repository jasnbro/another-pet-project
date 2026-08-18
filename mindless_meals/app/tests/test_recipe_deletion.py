"""Delete Recipe, including cleanup of anything that referenced it."""

RECIPE_PAYLOAD = {
    "name": "Air Fryer Salmon Bites",
    "cuisine": "East Asian",
    "effort": "easiest",
    "ingredients": "Salmon · rice · sesame",
    "method": "Air fry salmon → toss with sauce",
    "meal_types": ["dinner"],
}


def create_recipe(client, **overrides):
    payload = dict(RECIPE_PAYLOAD, **overrides)
    return client.post("/api/recipes", json=payload).get_json()["id"]


def test_delete_recipe_removes_it(client):
    recipe_id = create_recipe(client)

    res = client.delete(f"/api/recipes/{recipe_id}")
    assert res.status_code == 200
    assert res.get_json() == {"deleted": True, "id": recipe_id}

    listed = client.get("/api/recipes").get_json()
    assert listed == []


def test_delete_unknown_recipe_404s(client):
    res = client.delete("/api/recipes/999")
    assert res.status_code == 404


def test_delete_removes_its_favorite(client):
    recipe_id = create_recipe(client)
    client.post(f"/api/favorites/{recipe_id}")

    client.delete(f"/api/recipes/{recipe_id}")

    assert client.get("/api/favorites").get_json()["recipe_ids"] == []


def test_delete_removes_it_from_meal_plans(client):
    recipe_id = create_recipe(client)
    client.post("/api/meal-plans", json={"items": [{"recipe_id": recipe_id, "slot": "dinner"}]})

    client.delete(f"/api/recipes/{recipe_id}")

    # the plan's only item was this recipe, so the now-empty plan is gone too
    assert client.get("/api/meal-plans/current").get_json() is None


def test_delete_leaves_other_items_in_a_shared_plan(client):
    salmon_id = create_recipe(client)
    bowls_id = create_recipe(client, name="Gochujang Turkey Bowls", cuisine="East Asian")

    client.post(
        "/api/meal-plans",
        json={
            "items": [
                {"recipe_id": salmon_id, "slot": "dinner"},
                {"recipe_id": bowls_id, "slot": "lunch"},
            ]
        },
    )

    client.delete(f"/api/recipes/{salmon_id}")

    current = client.get("/api/meal-plans/current").get_json()
    assert current is not None
    assert len(current["items"]) == 1
    assert current["items"][0]["recipe_id"] == bowls_id
