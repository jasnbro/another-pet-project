"""Pydantic models for the YAML files in gym_log/data/.

Each model forbids unknown fields, so a typo in YAML (e.g. `rep:` for
`reps:`) fails validation instead of being silently ignored. Rules that
need more than one file (does this key exist? is it owned?) live in
loader.py.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LoadType = Literal["db_single", "db_per_hand", "bodyweight", "seconds", "band"]
EquipmentStatus = Literal["owned", "planned", "retired"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# What a "rep" means for each load type, for display.
LOAD_LABELS = {
    "db_single": "one dumbbell",
    "db_per_hand": "dumbbell per hand",
    "bodyweight": "bodyweight",
    "seconds": "timed hold (seconds)",
    "band": "band",
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Exercise(Strict):
    name: str = Field(min_length=1)
    what: str = Field(min_length=1)
    muscles: list[str]
    equipment: list[str]
    load: LoadType
    retired: bool = False
    alt: str | None = None


class Equipment(Strict):
    name: str = Field(min_length=1)
    status: EquipmentStatus
    notes: str | None = None


class PlanItem(Strict):
    key: str
    pair: str | None = None
    sets: int
    # [low, high]. For load: seconds this is seconds, not reps.
    reps: tuple[int, int]
    start: str | None = None
    cue: str | None = None

    @model_validator(mode="after")
    def _check_ranges(self):
        if self.sets < 1:
            raise ValueError(f"sets must be at least 1 (got {self.sets})")
        low, high = self.reps
        if low < 0 or high < 0:
            raise ValueError(f"reps can't be negative (got [{low}, {high}])")
        if low > high:
            raise ValueError(f"reps is [low, high]; low {low} is greater than high {high}")
        return self


class Schedule(Strict):
    odd: dict[Weekday, str]
    even: dict[Weekday, str]


class Progression(Strict):
    # "double": hit the top of the rep range on every set -> go up one jump.
    rule: Literal["double"]
    deload_every_weeks: int | None = Field(default=None, ge=1)


class Finisher(Strict):
    name: str
    rounds: int = Field(ge=1)
    work_sec: int = Field(ge=1)
    rest_sec: int = Field(ge=0)


class Plan(Strict):
    # Permanent id: sessions store it, and it must match the file name
    # (plans/<id>.yaml). Never change it; use `name` for what's displayed.
    plan: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1)
    active: bool = False
    starts: date
    session_minutes: int | None = Field(default=None, ge=1)
    schedule: Schedule
    warmup: list[str] = []
    progression: Progression
    days: dict[str, list[PlanItem]]
    finisher: Finisher | None = None

    @property
    def display_name(self) -> str:
        return self.name or self.plan

    @model_validator(mode="after")
    def _check_schedule_days(self):
        for parity in ("odd", "even"):
            for weekday, code in getattr(self.schedule, parity).items():
                if code not in self.days:
                    raise ValueError(
                        f"schedule.{parity}.{weekday} is day '{code}', but days: "
                        f"only defines {sorted(self.days)}"
                    )
        for code, items in self.days.items():
            if not items:
                raise ValueError(f"day '{code}' has no exercises")
            seen = set()
            for item in items:
                if item.key in seen:
                    raise ValueError(
                        f"day '{code}' lists '{item.key}' twice; each exercise "
                        "can appear once per day (sets are logged per key)"
                    )
                seen.add(item.key)
        return self
