"""JSON API under /api/gym. The front end (static/js/gym-log.js) is the only
client. The catalog (YAML) is loaded once at startup and lives at
current_app.extensions["gym_catalog"].
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, abort, current_app, jsonify, request, url_for

from .db import GymSession, GymSet, db
from .loader import Catalog
from .models import LOAD_LABELS
from .schedule import (
    CUE_TEXT,
    deload_sets,
    is_deload,
    next_session,
    plan_week,
    progression_cue,
    scheduled_day,
)

api = Blueprint("api", __name__, url_prefix="/api/gym")

# Fallback when the client doesn't say which date it means. The client
# always should: "today" is the iPad's local date, not the server's.
HOME_TZ = ZoneInfo("America/New_York")
WEIGHT_LIMIT = Decimal("9999.9")  # numeric(5,1)
SMALLINT_MAX = 32767


def catalog() -> Catalog:
    return current_app.extensions["gym_catalog"]


class Invalid(Exception):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


@api.errorhandler(Invalid)
def _invalid(exc):
    return jsonify({"error": str(exc)}), exc.status


def parse_date(value, what="date") -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise Invalid(f"{what} must be YYYY-MM-DD (got {value!r})", status=400) from None


def _num(value):
    if value is None:
        return None
    # numeric(5,1) -> JSON number: 25.0 -> 25, 22.5 -> 22.5
    value = Decimal(value)
    return int(value) if value == value.to_integral() else float(value)


# --- serialization ---------------------------------------------------------

def exercise_json(key):
    cat = catalog()
    ex = cat.exercises[key]
    return {
        "key": key,
        **ex.model_dump(mode="json"),
        "load_label": LOAD_LABELS[ex.load],
        "owned": cat.is_owned(key),
        "missing_equipment": cat.missing_equipment(key),
        # Illustration frames (start, mid, end) to loop; [] when there are none.
        "frames": [url_for("frames", filename=p) for p in cat.frames(key)],
    }


def set_json(s: GymSet):
    ex = catalog().exercises.get(s.exercise_key)
    return {
        "exercise_key": s.exercise_key,
        "name": ex.name if ex else s.exercise_key,
        "set_no": s.set_no,
        "weight": _num(s.weight),
        "band": s.band,
        "reps": s.reps,
    }


def session_json(s: GymSession):
    return {
        "date": s.session_date.isoformat(),
        "plan": s.plan,
        "day_code": s.day_code,
        "finished": s.finished,
        "warmup_done": list(s.warmup_done or []),
        "rope_rounds": list(s.rope_rounds or []),
        "notes": s.notes,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "sets": [set_json(x) for x in s.sets],
    }


# --- routes ----------------------------------------------------------------

@api.get("/catalog")
def get_catalog():
    cat = catalog()
    plan = cat.active_plan
    equipment = {}
    for key, eq in cat.equipment.items():
        equipment[key] = {
            "key": key,
            **eq.model_dump(mode="json"),
            "supports": [k for k, ex in cat.exercises.items() if key in ex.equipment],
        }
    return jsonify(
        {
            "exercises": {k: exercise_json(k) for k in cat.exercises},
            "equipment": equipment,
            "plan": plan.model_dump(mode="json"),
            "warnings": cat.warnings,
        }
    )


def _last_time(exercise_key, before: date):
    """Sets from the most recent earlier session that logged this exercise."""
    last_date = (
        db.session.query(GymSet.session_date)
        .filter(GymSet.exercise_key == exercise_key, GymSet.session_date < before)
        .order_by(GymSet.session_date.desc())
        .limit(1)
        .scalar()
    )
    if last_date is None:
        return None
    sets = (
        GymSet.query.filter_by(session_date=last_date, exercise_key=exercise_key)
        .order_by(GymSet.set_no)
        .all()
    )
    return {"date": last_date.isoformat(), "sets": [set_json(s) for s in sets]}


def _day_items(plan, code, deload, on: date):
    cat = catalog()
    items = []
    for item in plan.days[code]:
        key = cat.effective_key(item.key)
        ex = cat.exercises[key]
        sets = deload_sets(item.sets) if deload else item.sets
        last = _last_time(key, on)
        cue = None
        if last:
            cue = progression_cue(ex.load, [s["reps"] for s in last["sets"]], item.sets, item.reps[1])
        items.append(
            {
                **exercise_json(key),
                "planned_key": item.key,
                "swapped_for": cat.exercises[item.key].name if key != item.key else None,
                "pair": item.pair,
                "sets": sets,
                "planned_sets": item.sets,
                "reps": list(item.reps),
                "start": item.start,
                "cue": item.cue,
                "last": last,
                "progression": cue,
                "progression_text": CUE_TEXT.get((cue, ex.load)) if cue else None,
            }
        )
    return items


@api.get("/today")
def get_today():
    """The plan for one date: ?date=YYYY-MM-DD (the device's local date).
    ?day=A forces a day (manual override); otherwise an already-logged
    session's day wins, then the schedule."""
    cat = catalog()
    plan = cat.active_plan
    raw = request.args.get("date")
    on = parse_date(raw) if raw else datetime.now(HOME_TZ).date()
    override = request.args.get("day")
    if override is not None and override not in plan.days:
        raise Invalid(f"day must be one of {sorted(plan.days)} (got {override!r})", status=400)

    week = plan_week(plan, on)
    deload = is_deload(plan, week)
    scheduled = scheduled_day(plan, on)
    session = db.session.get(GymSession, on)
    code = override or (session.day_code if session and session.day_code in plan.days else None) or scheduled
    upcoming = next_session(plan, on)

    return jsonify(
        {
            "date": on.isoformat(),
            "plan": plan.plan,
            "plan_name": plan.display_name,
            "plan_starts": plan.starts.isoformat(),
            "week": week,
            "deload": deload,
            "deload_every_weeks": plan.progression.deload_every_weeks,
            "scheduled_day": scheduled,
            "day": code,
            "days": list(plan.days),
            "rest": code is None,
            "next": {"date": upcoming[0].isoformat(), "day": upcoming[1]} if upcoming else None,
            "warmup": plan.warmup,
            "finisher": plan.finisher.model_dump() if plan.finisher else None,
            "session_minutes": plan.session_minutes,
            "items": _day_items(plan, code, deload, on) if code else [],
            "session": session_json(session) if session else None,
        }
    )


@api.get("/sessions")
def list_sessions():
    query = GymSession.query
    since = request.args.get("since")
    if since:
        query = query.filter(GymSession.session_date >= parse_date(since, "since"))
    return jsonify([session_json(s) for s in query.order_by(GymSession.session_date.desc()).all()])


@api.get("/sessions/<day>")
def get_session(day):
    session = db.session.get(GymSession, parse_date(day))
    if session is None:
        abort(404)
    return jsonify(session_json(session))


def _bool_list(body, field):
    value = body.get(field, [])
    if not isinstance(value, list) or not all(isinstance(v, bool) for v in value):
        raise Invalid(f"{field} must be a list of true/false")
    return value


def _int_or_none(value, field, lo=0, hi=SMALLINT_MAX):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise Invalid(f"{field} must be a whole number (got {value!r})")
    if not lo <= value <= hi:
        raise Invalid(f"{field} must be between {lo} and {hi} (got {value})")
    return int(value)


def _parse_sets(raw_sets):
    cat = catalog()
    if not isinstance(raw_sets, list):
        raise Invalid("sets must be a list")
    sets, seen = [], set()
    for i, raw in enumerate(raw_sets):
        if not isinstance(raw, dict):
            raise Invalid(f"sets[{i}] must be an object")
        key = raw.get("exercise_key")
        if key not in cat.exercises:
            raise Invalid(f"sets[{i}]: unknown exercise key {key!r} (not in exercises.yaml)")
        set_no = _int_or_none(raw.get("set_no"), f"sets[{i}].set_no", lo=1)
        if set_no is None:
            raise Invalid(f"sets[{i}].set_no is required")
        if (key, set_no) in seen:
            raise Invalid(f"sets[{i}]: {key} set {set_no} appears twice")
        seen.add((key, set_no))

        weight = raw.get("weight")
        if weight is not None and weight != "":
            if isinstance(weight, bool):
                raise Invalid(f"sets[{i}].weight must be a number")
            try:
                weight = Decimal(str(weight)).quantize(Decimal("0.1"))
            except InvalidOperation:
                raise Invalid(f"sets[{i}].weight must be a number (got {weight!r})") from None
            if not 0 <= weight <= WEIGHT_LIMIT:
                raise Invalid(f"sets[{i}].weight must be between 0 and {WEIGHT_LIMIT} lb")
        else:
            weight = None
        band = raw.get("band")
        if band is not None and not isinstance(band, str):
            raise Invalid(f"sets[{i}].band must be text")
        band = (band or "").strip() or None
        reps = _int_or_none(raw.get("reps"), f"sets[{i}].reps")
        if weight is None and band is None and reps is None:
            continue  # an untouched row: nothing to log
        sets.append(GymSet(exercise_key=key, set_no=set_no, weight=weight, band=band, reps=reps))
    return sets


@api.put("/sessions/<day>")
def put_session(day):
    """Upsert one session and replace all its sets, in one transaction."""
    cat = catalog()
    on = parse_date(day)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise Invalid("body must be a JSON object", status=400)

    plan_id = body.get("plan") or cat.active_plan.plan
    if not isinstance(plan_id, str):
        raise Invalid("plan must be text")
    day_code = body.get("day_code")
    if not isinstance(day_code, str) or not day_code:
        raise Invalid("day_code is required (e.g. 'A')")
    finished = body.get("finished", False)
    if not isinstance(finished, bool):
        raise Invalid("finished must be true or false")
    notes = body.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise Invalid("notes must be text")
    warmup_done = _bool_list(body, "warmup_done")
    rope_rounds = _bool_list(body, "rope_rounds")
    sets = _parse_sets(body.get("sets", []))

    session = db.session.get(GymSession, on)
    if session is None:
        session = GymSession(session_date=on)
        db.session.add(session)
    session.plan = plan_id
    session.day_code = day_code
    session.finished = finished
    session.notes = (notes or "").strip() or None
    session.warmup_done = warmup_done
    session.rope_rounds = rope_rounds
    session.updated_at = datetime.now(HOME_TZ)
    session.sets = []
    db.session.flush()  # delete the old sets before inserting rows with the same keys
    session.sets = sets
    db.session.commit()
    return jsonify(session_json(session))


@api.get("/progress/<exercise_key>")
def progress(exercise_key):
    """Best set per session for one exercise, oldest first: heaviest weight,
    then most reps."""
    if exercise_key not in catalog().exercises:
        abort(404)
    rows = (
        GymSet.query.filter_by(exercise_key=exercise_key)
        .order_by(GymSet.session_date, GymSet.set_no)
        .all()
    )
    best = {}
    for s in rows:
        rank = (s.weight if s.weight is not None else Decimal(-1), s.reps if s.reps is not None else -1)
        if s.session_date not in best or rank > best[s.session_date][0]:
            best[s.session_date] = (rank, s)
    return jsonify(
        [
            {"date": d.isoformat(), **{k: v for k, v in set_json(s).items() if k != "name"}}
            for d, (_, s) in sorted(best.items())
        ]
    )


@api.get("/export.csv")
def export_csv():
    """Every logged set, one row per set. UTF-8 with a BOM so Excel reads the
    en dashes and the like correctly; Numbers ignores the BOM."""
    cat = catalog()
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(["date", "plan", "day", "exercise_key", "exercise_name", "set", "weight_lb", "band", "reps"])
    rows = (
        db.session.query(GymSet, GymSession)
        .join(GymSession, GymSet.session_date == GymSession.session_date)
        .order_by(GymSet.session_date, GymSet.exercise_key, GymSet.set_no)
        .all()
    )
    for s, sess in rows:
        ex = cat.exercises.get(s.exercise_key)
        weight = _num(s.weight)
        writer.writerow(
            [
                s.session_date.isoformat(),
                sess.plan,
                sess.day_code,
                s.exercise_key,
                ex.name if ex else "",
                s.set_no,
                "" if weight is None else weight,
                s.band or "",
                "" if s.reps is None else s.reps,
            ]
        )
    stamp = datetime.now(HOME_TZ).date().isoformat()
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="gym-log-{stamp}.csv"'},
    )

