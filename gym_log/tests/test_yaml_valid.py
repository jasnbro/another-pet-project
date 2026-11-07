"""CI gate for gym_log/data/: the real YAML must validate, and each rule in
the loader fails when broken (one test per rule, as issue #62 asks).
Validation never depends on the date: equipment ownership is a warning only."""
import pytest

from app.loader import CatalogError, load_catalog

from .conftest import DATA

PLAN = "plans/home-gym-v1.yaml"


def errors_for(data_dir):
    with pytest.raises(CatalogError) as exc:
        load_catalog(data_dir.path)
    return "\n".join(exc.value.errors)


# --- the real data ------------------------------------------------------------

def test_real_data_is_valid():
    """The actual files in gym_log/data. If this fails, the message says
    which file to fix."""
    catalog = load_catalog(DATA)
    assert catalog.active_plan


def test_seed_data_valid_with_everything_owned(data_dir):
    data_dir.own_everything()
    catalog = load_catalog(data_dir.path)
    assert catalog.warnings == []
    assert catalog.active_plan.plan == "home-gym-v1"


# --- rule: YAML parses, no unknown fields, no duplicate keys --------------------

def test_yaml_that_does_not_parse_fails(data_dir):
    data_dir.write("exercises.yaml", "goblet: { name: Goblet squat\n")
    assert "exercises.yaml: YAML doesn't parse" in errors_for(data_dir)


def test_unknown_field_fails(data_dir):
    data_dir.edit("exercises.yaml", lambda ex: ex["goblet"].update(musles=["quads"]))
    assert "exercises.yaml: goblet.musles: unknown field" in errors_for(data_dir)


def test_unknown_field_in_plan_fails(data_dir):
    data_dir.edit(PLAN, lambda p: p["days"]["A"][0].update(rep=[8, 12]))
    assert "days.A.0.rep: unknown field" in errors_for(data_dir)


def test_duplicate_key_fails(data_dir):
    text = (data_dir.path / "exercises.yaml").read_text(encoding="utf-8")
    data_dir.write("exercises.yaml", text + "goblet: { name: Again, what: x, muscles: [], equipment: [], load: bodyweight }\n")
    assert "duplicate key 'goblet'" in errors_for(data_dir)


def test_bad_enum_fails(data_dir):
    data_dir.edit("exercises.yaml", lambda ex: ex["goblet"].update(load="kettlebell"))
    assert "exercises.yaml: goblet.load" in errors_for(data_dir)


# --- rule: plan references an exercise key not in exercises.yaml -------------------

def test_plan_with_unknown_exercise_fails(data_dir):
    data_dir.edit(PLAN, lambda p: p["days"]["A"][0].update(key="goblett"))
    assert "day A uses 'goblett', which isn't in exercises.yaml" in errors_for(data_dir)


# --- rule: plan uses a retired exercise ----------------------------------------------

def test_plan_with_retired_exercise_fails(data_dir):
    data_dir.edit("exercises.yaml", lambda ex: ex["towel"].update(retired=True))
    assert "day A uses 'towel', which is retired" in errors_for(data_dir)


def test_retired_exercise_not_in_any_plan_is_fine(data_dir):
    data_dir.own_everything()
    data_dir.edit("exercises.yaml", lambda ex: ex.update(
        old_move={"name": "Old move", "what": "Gone.", "muscles": [], "equipment": [], "load": "bodyweight", "retired": True}))
    assert load_catalog(data_dir.path).exercises["old_move"].retired


# --- rule: exercise references an equipment key not in equipment.yaml ---------------

def test_exercise_with_unknown_equipment_fails(data_dir):
    data_dir.edit("exercises.yaml", lambda ex: ex["goblet"].update(equipment=["powerblocks", "kettlebell"]))
    assert "goblet uses equipment 'kettlebell', which isn't in equipment.yaml" in errors_for(data_dir)


# --- rule: active plan uses equipment that isn't owned --------------------------------

def test_active_plan_with_unowned_equipment_is_a_warning_not_an_error(data_dir):
    """Gear that hasn't arrived isn't broken data: it must never fail CI or
    stop the app, before or after the plan's start date."""
    data_dir.own_everything()
    data_dir.edit("equipment.yaml", lambda eq: eq["band_20_80"].update(status="planned"))
    catalog = load_catalog(data_dir.path)
    assert "plans/home-gym-v1.yaml: day B uses 'bandcurl', which needs equipment that isn't owned: band_20_80 (planned)" in catalog.warnings


def test_real_data_with_planned_gear_still_loads(data_dir):
    """Regression: with the seed data (powerblocks planned), validation used
    to flip from warning to error on the plan's start date (2026-11-09)."""
    catalog = load_catalog(data_dir.path)
    assert any("powerblocks (planned)" in w for w in catalog.warnings)


def test_unowned_equipment_with_an_owned_alt_is_fine(data_dir):
    """bench needs flybird_bench; with it planned, Day A swaps to floor_press."""
    data_dir.own_everything()
    data_dir.edit("equipment.yaml", lambda eq: eq["flybird_bench"].update(status="planned"))
    # Only bench has an alt, so park the other bench exercises in a plan
    # that uses no bench at all: keep the test about the swap.
    def strip(p):
        p["days"]["A"] = [i for i in p["days"]["A"] if i["key"] in ("goblet", "bench", "rdl", "towel", "deadbug")]
        p["days"]["B"] = [i for i in p["days"]["B"] if i["key"] in ("lunge", "bandcurl", "pushup", "hollow")]
    data_dir.edit(PLAN, strip)
    catalog = load_catalog(data_dir.path)
    assert catalog.effective_key("bench") == "floor_press"


# --- rule: more than one active plan --------------------------------------------------

def test_two_active_plans_fail(data_dir):
    plan = data_dir.load(PLAN)
    plan["plan"] = "home-gym-v2"
    data_dir.save("plans/home-gym-v2.yaml", plan)
    assert "more than one plan has active: true" in errors_for(data_dir)


def test_second_inactive_plan_is_fine(data_dir):
    data_dir.own_everything()
    plan = data_dir.load(PLAN)
    plan.update(plan="home-gym-v2", active=False)
    data_dir.save("plans/home-gym-v2.yaml", plan)
    assert set(load_catalog(data_dir.path).plans) == {"home-gym-v1", "home-gym-v2"}


def test_no_active_plan_fails(data_dir):
    data_dir.edit(PLAN, lambda p: p.update(active=False))
    assert "no plan has active: true" in errors_for(data_dir)


# --- rule: reps low > high, sets < 1 ------------------------------------------------------

def test_reps_low_above_high_fails(data_dir):
    data_dir.edit(PLAN, lambda p: p["days"]["A"][0].update(reps=[12, 8]))
    assert "low 12 is greater than high 8" in errors_for(data_dir)


def test_sets_below_one_fails(data_dir):
    data_dir.edit(PLAN, lambda p: p["days"]["A"][0].update(sets=0))
    assert "sets must be at least 1" in errors_for(data_dir)


# --- rule: alt points to an unknown or retired key, or one that isn't owned ------------------

def test_alt_to_unknown_key_fails(data_dir):
    data_dir.edit("exercises.yaml", lambda ex: ex["bench"].update(alt="floorpress"))
    assert "bench has alt 'floorpress', which isn't defined" in errors_for(data_dir)


def test_alt_to_retired_key_fails(data_dir):
    data_dir.edit("exercises.yaml", lambda ex: ex["floor_press"].update(retired=True))
    assert "bench has alt 'floor_press', which is retired" in errors_for(data_dir)


def test_alt_with_unowned_equipment_is_a_warning(data_dir):
    data_dir.own_everything()
    data_dir.edit("exercises.yaml", lambda ex: ex["floor_press"].update(equipment=["powerblocks", "foot_platform"]))
    data_dir.edit("equipment.yaml", lambda eq: eq["foot_platform"].update(status="planned"))
    catalog = load_catalog(data_dir.path)
    assert "exercises.yaml: bench's alt 'floor_press' needs equipment that isn't owned: foot_platform (planned)" in catalog.warnings


# --- extra safety rules ----------------------------------------------------------------------

def test_schedule_naming_a_missing_day_fails(data_dir):
    data_dir.edit(PLAN, lambda p: p["schedule"]["odd"].update(sat="C"))
    assert "schedule.odd.sat is day 'C'" in errors_for(data_dir)


def test_same_exercise_twice_in_a_day_fails(data_dir):
    data_dir.edit(PLAN, lambda p: p["days"]["A"].append(dict(p["days"]["A"][0], pair="Z1")))
    assert "day 'A' lists 'goblet' twice" in errors_for(data_dir)


def test_app_refuses_to_start_on_invalid_yaml(data_dir, make_app):
    data_dir.edit(PLAN, lambda p: p["days"]["A"][0].update(key="goblett"))
    with pytest.raises(SystemExit) as exc:
        make_app()
    assert "goblett" in str(exc.value)
