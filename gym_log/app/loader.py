"""Load and cross-validate the YAML in gym_log/data/.

The same check runs in CI (tests/test_yaml_valid.py) and at app startup;
the app refuses to start if it fails. Each problem is reported as one
plain-English line naming the file, so a CI failure says what to fix.

Rules (README.md "Reading a CI failure" explains each):
  - every file parses, has no unknown fields, and no duplicate keys
  - plans only use exercise keys defined in exercises.yaml, and none retired
  - exercises only use equipment keys defined in equipment.yaml
  - an exercise's `alt` is a known, non-retired key whose equipment is owned
  - exactly one plan has active: true
  - a plan's id (`plan:`) matches its file name; `name:` is the display name
  - the active plan only uses exercises whose equipment is owned (counting
    an automatic swap to `alt`)
The two ownership rules are always warnings, never errors: gear that hasn't
arrived yet isn't broken data, and must never block a deploy or stop the app
from starting. The app shows them on the Plan page ("Heads up") and on each
affected exercise card. Everything else is an error.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import Equipment, Exercise, Plan

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class CatalogError(Exception):
    """The YAML is invalid. str() is a ready-to-print report."""

    def __init__(self, errors, warnings=()):
        self.errors = list(errors)
        self.warnings = list(warnings)
        lines = ["Gym Log data in gym_log/data/ is invalid:"]
        lines += [f"  - {e}" for e in self.errors]
        if self.warnings:
            lines.append("Warnings:")
            lines += [f"  - {w}" for w in self.warnings]
        super().__init__("\n".join(lines))


@dataclass(frozen=True)
class Catalog:
    exercises: dict[str, Exercise]
    equipment: dict[str, Equipment]
    plans: dict[str, Plan]
    warnings: list[str] = field(default_factory=list)

    @property
    def active_plan(self) -> Plan:
        return next(p for p in self.plans.values() if p.active)

    def is_owned(self, exercise_key: str) -> bool:
        """True when every piece of the exercise's equipment is owned."""
        ex = self.exercises[exercise_key]
        return all(self.equipment[k].status == "owned" for k in ex.equipment)

    def missing_equipment(self, exercise_key: str) -> list[str]:
        ex = self.exercises[exercise_key]
        return [k for k in ex.equipment if self.equipment[k].status != "owned"]

    def effective_key(self, exercise_key: str) -> str:
        """The key actually trained: the exercise's `alt` when any of its
        equipment isn't owned and it has one, otherwise itself."""
        ex = self.exercises[exercise_key]
        if ex.alt and not self.is_owned(exercise_key):
            return ex.alt
        return exercise_key


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys. Plain PyYAML keeps the
    last one silently, which would let a second `goblet:` quietly replace
    the first."""


def _construct_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key '{key}'", key_node.start_mark
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _read_yaml(path: Path, errors: list[str]):
    try:
        with path.open(encoding="utf-8") as f:
            return yaml.load(f, Loader=_UniqueKeyLoader)
    except FileNotFoundError:
        errors.append(f"{path.name}: file not found")
    except yaml.YAMLError as exc:
        errors.append(f"{path.name}: YAML doesn't parse: {' '.join(str(exc).split())}")
    return None


def _pydantic_errors(where: str, exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        if err["type"] == "extra_forbidden":
            msg = "unknown field (typo?)"
        out.append(f"{where}{'.' + loc if loc else ''}: {msg}")
    return out


def _parse_mapping(path: Path, model, errors: list[str]) -> dict:
    raw = _read_yaml(path, errors)
    if raw is None:
        if path.exists() and not errors:
            errors.append(f"{path.name}: file is empty")
        return {}
    if not isinstance(raw, dict):
        errors.append(f"{path.name}: expected a mapping of key: {{...}} entries")
        return {}
    parsed = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            errors.append(f"{path.name}: key {key!r} must be text")
            continue
        try:
            parsed[key] = model.model_validate(value if value is not None else {})
        except ValidationError as exc:
            errors.extend(_pydantic_errors(f"{path.name}: {key}", exc))
    return parsed


def load_catalog(data_dir: Path | str | None = None) -> Catalog:
    """Load everything under data_dir and validate it. Raises CatalogError
    listing every problem found (not just the first)."""
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    errors: list[str] = []
    warnings: list[str] = []

    equipment = _parse_mapping(data_dir / "equipment.yaml", Equipment, errors)
    exercises = _parse_mapping(data_dir / "exercises.yaml", Exercise, errors)

    plans: dict[str, Plan] = {}
    plan_files: dict[str, str] = {}
    plan_paths = sorted((data_dir / "plans").glob("*.yaml"))
    if not plan_paths:
        errors.append("plans/: no plan files (*.yaml) found")
    for path in plan_paths:
        where = f"plans/{path.name}"
        raw = _read_yaml(path, errors)
        if raw is None:
            continue
        try:
            plan = Plan.model_validate(raw)
        except ValidationError as exc:
            errors.extend(_pydantic_errors(where, exc))
            continue
        if plan.plan != path.stem:
            errors.append(
                f"{where}: plan id '{plan.plan}' must match the file name ('{path.stem}'). "
                "The id is permanent (logged sessions store it); to rename the plan, "
                f"set name: {plan.plan} instead and put back plan: {path.stem}"
            )
            continue
        if plan.plan in plans:
            errors.append(f"{where}: plan id '{plan.plan}' is already used by plans/{plan_files[plan.plan]}")
            continue
        plans[plan.plan] = plan
        plan_files[plan.plan] = path.name

    # --- exercises -> equipment, alt ------------------------------------
    for key, ex in exercises.items():
        for eq in ex.equipment:
            if eq not in equipment:
                errors.append(f"exercises.yaml: {key} uses equipment '{eq}', which isn't in equipment.yaml")

    def owned(key):
        return all(equipment.get(k) is not None and equipment[k].status == "owned" for k in exercises[key].equipment)

    ownership: list[str] = []  # always warnings (see the module docstring)
    for key, ex in exercises.items():
        if ex.alt is None:
            continue
        if ex.alt == key:
            errors.append(f"exercises.yaml: {key} lists itself as its own alt")
        elif ex.alt not in exercises:
            errors.append(f"exercises.yaml: {key} has alt '{ex.alt}', which isn't defined")
        elif exercises[ex.alt].retired:
            errors.append(f"exercises.yaml: {key} has alt '{ex.alt}', which is retired")
        elif not owned(ex.alt):
            missing = [k for k in exercises[ex.alt].equipment if k in equipment and equipment[k].status != "owned"]
            ownership.append(
                f"exercises.yaml: {key}'s alt '{ex.alt}' needs equipment that isn't owned: "
                + ", ".join(f"{k} ({equipment[k].status})" for k in missing)
            )

    # --- plans -> exercises ----------------------------------------------
    for plan_id, plan in plans.items():
        where = f"plans/{plan_files[plan_id]}"
        for code, items in plan.days.items():
            for item in items:
                if item.key not in exercises:
                    errors.append(f"{where}: day {code} uses '{item.key}', which isn't in exercises.yaml")
                elif exercises[item.key].retired:
                    errors.append(f"{where}: day {code} uses '{item.key}', which is retired")

    active = [p for p in plans.values() if p.active]
    if len(active) > 1:
        errors.append(
            "more than one plan has active: true: "
            + ", ".join(f"plans/{plan_files[p.plan]}" for p in active)
            + " (set active: false on all but one)"
        )
    elif not active and plans:
        errors.append("no plan has active: true (set it on the plan you're training)")

    # --- the active plan's equipment ---------------------------------------
    if len(active) == 1:
        plan = active[0]
        where = f"plans/{plan_files[plan.plan]}"
        for code, items in plan.days.items():
            trained = {}
            for item in items:
                ex = exercises.get(item.key)
                if ex is None or ex.retired or any(k not in equipment for k in ex.equipment):
                    continue  # already reported above
                key = item.key
                if not owned(key) and ex.alt in exercises:
                    key = ex.alt  # swapped automatically; the alt is checked instead
                if key in trained:
                    errors.append(
                        f"{where}: day {code} would train '{key}' twice ('{trained[key]}' and "
                        f"'{item.key}', after swapping to alt)"
                    )
                trained[key] = item.key
                if not owned(key):
                    missing = [k for k in exercises[key].equipment if equipment[k].status != "owned"]
                    via = f" (swapped in for {item.key})" if key != item.key else ""
                    ownership.append(
                        f"{where}: day {code} uses '{key}'{via}, which needs equipment that isn't owned: "
                        + ", ".join(f"{k} ({equipment[k].status})" for k in missing)
                    )

    warnings.extend(dict.fromkeys(ownership))  # de-duplicate, keep order

    if errors:
        raise CatalogError(errors, warnings)
    return Catalog(exercises=exercises, equipment=equipment, plans=plans, warnings=warnings)
