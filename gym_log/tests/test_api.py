"""API: logging persists, last time + cues, swaps, history, CSV."""
import csv
import io

PUT = "/api/gym/sessions/"


def log(client, day, sets, day_code="A", **extra):
    body = {"day_code": day_code, "sets": sets, **extra}
    return client.put(PUT + day, json=body)


def sets_of(key, *pairs):
    return [{"exercise_key": key, "set_no": i + 1, "weight": w, "reps": r} for i, (w, r) in enumerate(pairs)]


def test_log_then_history(client):
    r = log(client, "2026-11-09", sets_of("goblet", (25, 12), (25, 11)),
            notes="  felt good ", warmup_done=[True, True], rope_rounds=[True, False], finished=True)
    assert r.status_code == 200, r.json
    history = client.get("/api/gym/sessions").json
    assert len(history) == 1
    s = history[0]
    assert s["date"] == "2026-11-09" and s["day_code"] == "A" and s["plan"] == "home-gym-v1"
    assert s["notes"] == "felt good" and s["finished"] is True
    assert s["warmup_done"] == [True, True] and s["rope_rounds"] == [True, False]
    assert [(x["set_no"], x["weight"], x["reps"]) for x in s["sets"]] == [(1, 25, 12), (2, 25, 11)]


def test_put_replaces_all_sets(client):
    log(client, "2026-11-09", sets_of("goblet", (25, 12), (25, 12), (25, 12)))
    log(client, "2026-11-09", sets_of("goblet", (30, 8)))
    sets = client.get(PUT + "2026-11-09").json["sets"]
    assert [(x["weight"], x["reps"]) for x in sets] == [(30, 8)]


def test_empty_rows_are_not_stored(client):
    log(client, "2026-11-09", [{"exercise_key": "goblet", "set_no": 1, "weight": None, "reps": None}])
    assert client.get(PUT + "2026-11-09").json["sets"] == []


def test_unknown_exercise_key_is_422(client):
    r = log(client, "2026-11-09", sets_of("goblett", (25, 12)))
    assert r.status_code == 422
    assert "goblett" in r.json["error"]
    assert client.get("/api/gym/sessions").json == []


def test_bad_values_are_rejected(client):
    assert log(client, "2026-11-09", sets_of("goblet", ("heavy", 12))).status_code == 422
    assert log(client, "2026-11-09", sets_of("goblet", (25, 12.5))).status_code == 422
    assert log(client, "2026-11-09", sets_of("goblet", (25, 12), (25, 12)) * 2).status_code == 422
    assert log(client, "2026-11-09", [], day_code="").status_code == 422
    assert client.put(PUT + "2026-13-40", json={"day_code": "A"}).status_code == 400


def test_since_filter_and_newest_first(client):
    for d in ("2026-11-09", "2026-11-11", "2026-11-13"):
        log(client, d, sets_of("goblet", (25, 10)))
    dates = [s["date"] for s in client.get("/api/gym/sessions?since=2026-11-11").json]
    assert dates == ["2026-11-13", "2026-11-11"]


def test_today_uses_the_schedule_and_the_client_date(client):
    t = client.get("/api/gym/today?date=2026-11-09").json
    assert (t["day"], t["week"], t["deload"], t["rest"]) == ("A", 1, False, False)
    assert [i["key"] for i in t["items"]][:2] == ["goblet", "bench"]
    rest = client.get("/api/gym/today?date=2026-11-10").json
    assert rest["rest"] and rest["next"] == {"date": "2026-11-11", "day": "B"}
    assert client.get("/api/gym/today?date=2026-11-10&day=B").json["day"] == "B"
    assert client.get("/api/gym/today?date=2026-11-10&day=Q").status_code == 400


def test_logged_day_wins_over_schedule(client):
    log(client, "2026-11-09", sets_of("lunge", (10, 8)), day_code="B")
    assert client.get("/api/gym/today?date=2026-11-09").json["day"] == "B"


def test_deload_halves_sets(client):
    t = client.get("/api/gym/today?date=2027-01-04").json
    assert t["deload"] and t["week"] == 9
    goblet = t["items"][0]
    assert (goblet["sets"], goblet["planned_sets"]) == (2, 3)


def test_last_time_and_progression_cue(client):
    log(client, "2026-11-09", sets_of("goblet", (25, 12), (25, 12), (25, 12)) + sets_of("rdl", (20, 12), (20, 10), (20, 9)))
    t = client.get("/api/gym/today?date=2026-11-13").json  # next Day A
    items = {i["key"]: i for i in t["items"]}
    assert items["goblet"]["last"]["date"] == "2026-11-09"
    assert [s["weight"] for s in items["goblet"]["last"]["sets"]] == [25, 25, 25]
    assert items["goblet"]["progression"] == "up"
    assert items["goblet"]["progression_text"] == "Top of the range on every set: go up a jump."
    assert items["rdl"]["progression"] == "same"
    assert items["rdl"]["progression_text"] == "Same weight, beat last reps."
    assert items["csrow"]["last"] is None and items["csrow"]["progression"] is None
    # The same day's own session isn't "last time".
    assert client.get("/api/gym/today?date=2026-11-09").json["items"][0]["last"] is None


def test_swap_to_alt_when_bench_not_owned(make_app, data_dir):
    data_dir.own_everything()
    data_dir.edit("equipment.yaml", lambda eq: eq["flybird_bench"].update(status="planned"))
    client = make_app().test_client()  # unowned gear is only a warning
    items = client.get("/api/gym/today?date=2026-11-09").json["items"]
    a2 = items[1]
    assert (a2["key"], a2["planned_key"], a2["swapped_for"]) == ("floor_press", "bench", "Dumbbell bench press")
    assert a2["name"] == "Dumbbell floor press"
    # and it logs under the alt's key
    assert log(client, "2026-11-09", sets_of("floor_press", (20, 10))).status_code == 200


def test_no_swap_when_bench_owned(client):
    assert client.get("/api/gym/today?date=2026-11-09").json["items"][1]["key"] == "bench"


def test_catalog(client):
    c = client.get("/api/gym/catalog").json
    assert c["plan"]["plan"] == "home-gym-v1"
    assert c["exercises"]["goblet"]["what"].startswith("Squat holding")
    assert "goblet" in c["equipment"]["squat_wedges"]["supports"]
    assert c["exercises"]["towel"]["equipment"] == []


def test_progress_best_set_per_session(client):
    log(client, "2026-11-09", sets_of("goblet", (25, 12), (30, 6), (30, 8)))
    log(client, "2026-11-13", sets_of("goblet", (30, 10)))
    p = client.get("/api/gym/progress/goblet").json
    assert [(x["date"], x["weight"], x["reps"]) for x in p] == [("2026-11-09", 30, 8), ("2026-11-13", 30, 10)]
    assert client.get("/api/gym/progress/nope").status_code == 404


def test_csv_export_one_row_per_set(client):
    log(client, "2026-11-09", sets_of("goblet", (22.5, 12), (25, 10)))
    log(client, "2026-11-11", [{"exercise_key": "bandcurl", "set_no": 1, "band": "red", "reps": 15}], day_code="B")
    r = client.get("/api/gym/export.csv")
    assert r.mimetype == "text/csv" and "attachment" in r.headers["Content-Disposition"]
    text = r.data.decode("utf-8")
    assert text.startswith("﻿")  # Excel needs the BOM to read UTF-8
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows[0] == ["date", "plan", "day", "exercise_key", "exercise_name", "set", "weight_lb", "band", "reps"]
    assert rows[1:] == [
        ["2026-11-09", "home-gym-v1", "A", "goblet", "Goblet squat", "1", "22.5", "", "12"],
        ["2026-11-09", "home-gym-v1", "A", "goblet", "Goblet squat", "2", "25", "", "10"],
        ["2026-11-11", "home-gym-v1", "B", "bandcurl", "Prone band leg curl", "1", "", "red", "15"],
    ]


def test_rep_range_change_needs_no_code(make_app, data_dir):
    data_dir.own_everything()
    data_dir.edit("plans/home-gym-v1.yaml", lambda p: p["days"]["A"][0].update(reps=[6, 10]))
    items = make_app().test_client().get("/api/gym/today?date=2026-11-09").json["items"]
    assert items[0]["reps"] == [6, 10]
