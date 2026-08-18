"""Favorites: persistence (product spec §10)."""

RECIPE_PAYLOAD = {
    "name": "Miso Salmon Bowls",
    "cuisine": "East Asian",
    "effort": "easy",
    "ingredients": "Salmon · rice · cucumber",
    "method": "Roast salmon → assemble bowls",
}


def create_recipe(client):
    return client.post("/api/recipes", json=RECIPE_PAYLOAD).get_json()["id"]


def test_favoriting_persists_across_requests(client):
    recipe_id = create_recipe(client)

    res = client.post(f"/api/favorites/{recipe_id}")
    assert res.status_code == 200
    assert res.get_json() == {"recipe_id": recipe_id, "favorited": True}

    listed = client.get("/api/favorites").get_json()
    assert listed["recipe_ids"] == [recipe_id]


def test_favoriting_twice_does_not_duplicate(client):
    recipe_id = create_recipe(client)
    client.post(f"/api/favorites/{recipe_id}")
    client.post(f"/api/favorites/{recipe_id}")

    listed = client.get("/api/favorites").get_json()
    assert listed["recipe_ids"] == [recipe_id]


def test_unfavoriting_removes_it(client):
    recipe_id = create_recipe(client)
    client.post(f"/api/favorites/{recipe_id}")

    res = client.delete(f"/api/favorites/{recipe_id}")
    assert res.status_code == 200
    assert res.get_json() == {"recipe_id": recipe_id, "favorited": False}
    assert client.get("/api/favorites").get_json()["recipe_ids"] == []


def test_favoriting_unknown_recipe_404s(client):
    res = client.post("/api/favorites/999")
    assert res.status_code == 404
