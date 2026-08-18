"""Add/Edit Recipe: creation, update, and validation (product spec §12)."""


def valid_payload(**overrides):
    payload = {
        "name": "Gochujang Turkey Bowls",
        "cuisine": "East Asian",
        "effort": "easy",
        "ingredients": "Ground turkey · broccoli · rice",
        "sauce": "Gochujang · soy · garlic",
        "method": "Stir fry everything → serve over rice",
        "meal_types": ["lunch", "dinner"],
        "other_tags": ["High Protein", "reheat"],
    }
    payload.update(overrides)
    return payload


def test_create_recipe_persists_and_is_listed(client):
    res = client.post("/api/recipes", json=valid_payload())
    assert res.status_code == 201
    created = res.get_json()
    assert created["name"] == "Gochujang Turkey Bowls"
    assert created["effort_label"] == "Easy"
    # free-text tags are slugified and deduplicated alongside known ones
    assert sorted(created["other_tags"]) == ["high-protein", "reheat"]

    listed = client.get("/api/recipes").get_json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


def test_sauce_is_optional(client):
    res = client.post("/api/recipes", json=valid_payload(sauce=""))
    assert res.status_code == 201
    assert res.get_json()["sauce"] is None


def test_missing_required_field_is_rejected(client):
    for field in ["name", "cuisine", "ingredients", "method"]:
        res = client.post("/api/recipes", json=valid_payload(**{field: "  "}))
        assert res.status_code == 400, f"expected {field} to be required"
        assert "error" in res.get_json()

    # nothing should have been persisted by the failed attempts
    assert client.get("/api/recipes").get_json() == []


def test_invalid_effort_is_rejected(client):
    res = client.post("/api/recipes", json=valid_payload(effort="extremely-hard"))
    assert res.status_code == 400


def test_unknown_meal_types_are_dropped_not_rejected(client):
    res = client.post("/api/recipes", json=valid_payload(meal_types=["lunch", "elevenses"]))
    assert res.status_code == 201
    assert res.get_json()["meal_types"] == ["lunch"]


def test_source_url_is_optional(client):
    res = client.post("/api/recipes", json=valid_payload())
    assert res.status_code == 201
    assert res.get_json()["source_url"] is None


def test_source_url_is_persisted_when_valid(client):
    res = client.post(
        "/api/recipes", json=valid_payload(source_url="https://www.tiktok.com/@someone/video/123")
    )
    assert res.status_code == 201
    assert res.get_json()["source_url"] == "https://www.tiktok.com/@someone/video/123"


def test_source_url_without_scheme_is_rejected(client):
    res = client.post("/api/recipes", json=valid_payload(source_url="tiktok.com/@someone/video/123"))
    assert res.status_code == 400


def test_update_recipe_persists_changes(client):
    created = client.post("/api/recipes", json=valid_payload()).get_json()

    res = client.put(
        "/api/recipes/" + str(created["id"]),
        json=valid_payload(
            name="Gochujang Turkey Bowls (updated)",
            effort="moderate",
            source_url="https://example.com/gochujang-bowls",
        ),
    )
    assert res.status_code == 200
    updated = res.get_json()
    assert updated["id"] == created["id"]
    assert updated["name"] == "Gochujang Turkey Bowls (updated)"
    assert updated["effort"] == "moderate"
    assert updated["source_url"] == "https://example.com/gochujang-bowls"

    # the change is durable, not just the response echo
    listed = client.get("/api/recipes").get_json()
    assert len(listed) == 1
    assert listed[0]["name"] == "Gochujang Turkey Bowls (updated)"


def test_update_unknown_recipe_404s(client):
    res = client.put("/api/recipes/999", json=valid_payload())
    assert res.status_code == 404


def test_update_rejects_invalid_payload_without_changing_recipe(client):
    created = client.post("/api/recipes", json=valid_payload()).get_json()

    res = client.put("/api/recipes/" + str(created["id"]), json=valid_payload(name=""))
    assert res.status_code == 400

    listed = client.get("/api/recipes").get_json()
    assert listed[0]["name"] == "Gochujang Turkey Bowls"
