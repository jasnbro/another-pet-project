"""Compact Make formatting: server-side safety net for direct API calls
that bypass the UI's own normalization (product spec v1.1 §2)."""


def valid_payload(**overrides):
    payload = {
        "name": "Salmon Rice Bowls",
        "cuisine": "East Asian",
        "effort": "easy",
        "ingredients": "Salmon · rice · cucumber",
        "method": "Cook salmon → dice vegetables → assemble",
    }
    payload.update(overrides)
    return payload


def test_method_separators_are_normalized_to_arrows(client):
    res = client.post(
        "/api/recipes",
        json=valid_payload(method="Roast sweet potatoes, brown turkey; assemble bowls"),
    )
    assert res.status_code == 201
    assert res.get_json()["method"] == "Roast sweet potatoes → Brown turkey → Assemble bowls"


def test_method_newlines_are_normalized_to_arrows(client):
    res = client.post("/api/recipes", json=valid_payload(method="Bake meatballs\nSimmer in gravy"))
    assert res.status_code == 201
    assert res.get_json()["method"] == "Bake meatballs → Simmer in gravy"


def test_method_ascii_arrow_is_normalized(client):
    res = client.post(
        "/api/recipes", json=valid_payload(method="Cook salmon -> dice vegetables -> assemble")
    )
    assert res.status_code == 201
    assert res.get_json()["method"] == "Cook salmon → Dice vegetables → Assemble"


def test_method_is_idempotent_on_already_formatted_text(client):
    formatted = "Sauté cabbage → Add sauce → Serve over rice"
    res = client.post("/api/recipes", json=valid_payload(method=formatted))
    assert res.status_code == 201
    assert res.get_json()["method"] == formatted


def test_blank_method_is_still_rejected(client):
    res = client.post("/api/recipes", json=valid_payload(method="  ,, ;  "))
    assert res.status_code == 400
