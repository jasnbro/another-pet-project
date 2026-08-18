"""Save Meal Plan: persistence and "reopen current plan" (product spec §11)."""

RECIPE_PAYLOAD = {
    "name": "Freezer Dumpling Bowls",
    "cuisine": "East Asian",
    "effort": "easiest",
    "ingredients": "Frozen dumplings · edamame · greens",
    "method": "Steam everything → add to bowl → add sauce",
}


def create_recipe(client):
    return client.post("/api/recipes", json=RECIPE_PAYLOAD).get_json()["id"]


def test_no_saved_plan_returns_null(client):
    assert client.get("/api/meal-plans/current").get_json() is None


def test_saving_a_plan_makes_it_the_current_one(client):
    recipe_id = create_recipe(client)

    res = client.post("/api/meal-plans", json={"items": [{"recipe_id": recipe_id, "slot": "lunch"}]})
    assert res.status_code == 201
    saved = res.get_json()
    assert len(saved["items"]) == 1
    assert saved["items"][0]["recipe_id"] == recipe_id
    assert saved["items"][0]["slot"] == "lunch"

    current = client.get("/api/meal-plans/current").get_json()
    assert current["id"] == saved["id"]


def test_saving_a_second_plan_replaces_current(client):
    recipe_id = create_recipe(client)
    client.post("/api/meal-plans", json={"items": [{"recipe_id": recipe_id, "slot": "lunch"}]})
    second = client.post(
        "/api/meal-plans", json={"items": [{"recipe_id": recipe_id, "slot": "dinner"}]}
    ).get_json()

    current = client.get("/api/meal-plans/current").get_json()
    assert current["id"] == second["id"]
    assert current["items"][0]["slot"] == "dinner"


def test_empty_plan_is_rejected(client):
    res = client.post("/api/meal-plans", json={"items": []})
    assert res.status_code == 400


def test_unknown_recipe_in_plan_is_rejected(client):
    res = client.post("/api/meal-plans", json={"items": [{"recipe_id": 999, "slot": "lunch"}]})
    assert res.status_code == 400
    # nothing should have been persisted
    assert client.get("/api/meal-plans/current").get_json() is None


def test_invalid_slot_is_stored_as_unassigned(client):
    recipe_id = create_recipe(client)
    res = client.post(
        "/api/meal-plans", json={"items": [{"recipe_id": recipe_id, "slot": "brunch"}]}
    )
    assert res.status_code == 201
    assert res.get_json()["items"][0]["slot"] is None
