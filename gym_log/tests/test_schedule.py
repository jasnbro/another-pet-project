"""A/B rotation, deload weeks, and the progression cue."""
from datetime import date, timedelta

from app.loader import load_catalog
from app.schedule import deload_sets, is_deload, next_session, plan_week, progression_cue, scheduled_day

from .conftest import DATA

PLAN = load_catalog(DATA).plans["home-gym-v1"]  # starts Mon 2026-11-09


def mondays(start, count):
    return [start + timedelta(weeks=i) for i in range(count)]


def test_week_one_is_the_start_week():
    assert plan_week(PLAN, date(2026, 11, 9)) == 1
    assert plan_week(PLAN, date(2026, 11, 15)) == 1
    assert plan_week(PLAN, date(2026, 11, 16)) == 2
    assert plan_week(PLAN, date(2026, 11, 8)) is None


def test_first_weeks_follow_the_plan():
    assert [scheduled_day(PLAN, date(2026, 11, d)) for d in (9, 10, 11, 13, 14)] == ["A", None, "B", "A", None]
    assert [scheduled_day(PLAN, date(2026, 11, d)) for d in (16, 18, 20)] == ["B", "A", "B"]


def test_rotation_is_continuous_across_a_53_week_iso_year():
    """2026 has an ISO week 53 (Dec 28 - Jan 3). Counting ISO weeks would
    make ISO week 53 and ISO week 1 both odd and repeat a Monday. Plan
    weeks keep alternating."""
    assert date(2026, 12, 28).isocalendar().week == 53
    assert date(2027, 1, 4).isocalendar().week == 1
    days = [scheduled_day(PLAN, m) for m in mondays(date(2026, 11, 9), 60)]
    assert days == ["A", "B"] * 30
    # The ISO approach really would have broken here:
    iso_odd = [d.isocalendar().week % 2 == 1 for d in (date(2026, 12, 28), date(2027, 1, 4))]
    assert iso_odd == [True, True]
    assert scheduled_day(PLAN, date(2026, 12, 28)) != scheduled_day(PLAN, date(2027, 1, 4))


def test_rotation_continuous_across_a_normal_year_boundary_too():
    days = [scheduled_day(PLAN, m) for m in mondays(date(2026, 11, 9), 120)]
    assert all(a != b for a, b in zip(days, days[1:]))


def test_deload_every_ninth_week():
    week9 = date(2026, 11, 9) + timedelta(weeks=8)
    assert week9 == date(2027, 1, 4)
    assert is_deload(PLAN, plan_week(PLAN, week9))
    assert is_deload(PLAN, plan_week(PLAN, week9 + timedelta(days=6)))
    assert not is_deload(PLAN, plan_week(PLAN, week9 - timedelta(days=1)))
    assert not is_deload(PLAN, plan_week(PLAN, week9 + timedelta(days=7)))
    assert is_deload(PLAN, 18)
    assert not is_deload(PLAN, None)


def test_deload_halves_sets_rounding_up():
    assert [deload_sets(n) for n in (1, 2, 3, 4, 5)] == [1, 1, 2, 2, 3]


def test_next_session():
    assert next_session(PLAN, date(2026, 11, 1)) == (date(2026, 11, 9), "A")
    assert next_session(PLAN, date(2026, 11, 9)) == (date(2026, 11, 11), "B")
    assert next_session(PLAN, date(2026, 11, 14)) == (date(2026, 11, 16), "B")


def test_progression_cue():
    assert progression_cue("db_single", [], 3, 12) is None
    assert progression_cue("db_single", [12, 12, 12], 3, 12) == "up"
    assert progression_cue("db_single", [12, 12, 13], 3, 12) == "up"
    assert progression_cue("db_single", [12, 12, 11], 3, 12) == "same"
    assert progression_cue("db_single", [12, 12], 3, 12) == "same"  # a set short
    assert progression_cue("db_single", [12, 12, None], 3, 12) == "same"
