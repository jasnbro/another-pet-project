"""Which day is it? Pure functions over a Plan and a date.

Plan week = whole weeks since the plan's `starts` date, week 1 = odd.
Never ISO week numbers: an ISO year with a week 53 (2026 is one) would
put two odd weeks back to back and repeat A/B.
"""
import math
from datetime import date, timedelta

from .models import WEEKDAYS, Plan


def plan_week(plan: Plan, day: date) -> int | None:
    """1-based week number within the plan, or None before it starts."""
    if day < plan.starts:
        return None
    return (day - plan.starts).days // 7 + 1


def is_deload(plan: Plan, week: int | None) -> bool:
    every = plan.progression.deload_every_weeks
    return bool(week and every and week % every == 0)


def deload_sets(sets: int) -> int:
    """Deload weeks halve the sets, rounding up (3 -> 2, 2 -> 1)."""
    return math.ceil(sets / 2)


def scheduled_day(plan: Plan, day: date) -> str | None:
    """The day code ('A', 'B', ...) scheduled on `day`, or None for rest."""
    week = plan_week(plan, day)
    if week is None:
        return None
    week_schedule = plan.schedule.odd if week % 2 == 1 else plan.schedule.even
    return week_schedule.get(WEEKDAYS[day.weekday()])


def next_session(plan: Plan, after: date) -> tuple[date, str] | None:
    """The first scheduled (date, day code) strictly after `after`."""
    day = max(after + timedelta(days=1), plan.starts)
    for _ in range(14):  # both schedule weeks
        code = scheduled_day(plan, day)
        if code:
            return day, code
        day += timedelta(days=1)
    return None


def progression_cue(load: str, last_reps: list[int | None], planned_sets: int, reps_high: int) -> str | None:
    """Double progression: every set at the top of the range -> go up.

    `last_reps` are the reps (or seconds) logged per set last time.
    Returns "up", "same", or None when there's nothing to compare with.
    """
    logged = [r for r in last_reps if r is not None]
    if not logged:
        return None
    if len(logged) >= planned_sets and all(r >= reps_high for r in logged):
        return "up"
    return "same"


CUE_TEXT = {
    ("up", "db_single"): "Top of the range on every set: go up a jump.",
    ("up", "db_per_hand"): "Top of the range on every set: go up a jump.",
    ("up", "band"): "Top of the range on every set: go up a band.",
    ("up", "bodyweight"): "Top of the range on every set: make it harder.",
    ("up", "seconds"): "Top of the range on every set: hold longer or make it harder.",
    ("same", "db_single"): "Same weight, beat last reps.",
    ("same", "db_per_hand"): "Same weight, beat last reps.",
    ("same", "band"): "Same band, beat last reps.",
    ("same", "bodyweight"): "Beat last reps.",
    ("same", "seconds"): "Beat last time.",
}
