"""Whose data a request sees, and the read-only demo.

- Signed in with access to Gym Log: your own sessions, read and write.
- Anyone else (signed out, or an account without the Gym Log grant): the
  demo account's sample sessions, read-only. Visitors from the Undercurrent
  landing page never see anyone's real data.

Accounts come from the shared Undercurrent identity (undercurrent_identity,
copied in by shared/undercurrent-identity/sync.sh).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import current_app

from .db import DEMO_USER, GymSession, GymSet, db
from .schedule import deload_sets, is_deload, plan_week, scheduled_day

APP_NAME = "gym_log"
DEMO_WEEKS = 3


@dataclass(frozen=True)
class Viewer:
    user_id: str
    can_write: bool
    signed_in: bool
    name: str | None

    @property
    def demo(self) -> bool:
        return self.user_id == DEMO_USER


def identity():
    return current_app.extensions["undercurrent_identity"]


def viewer() -> Viewer:
    ident = identity()
    user = ident.current_user()
    if user and user.can_use(APP_NAME):
        return Viewer(user.id, True, True, user.display_name)
    return Viewer(DEMO_USER, False, user is not None, user.display_name if user else None)


# --- demo data -------------------------------------------------------------

def ensure_demo(today: date) -> None:
    """Keep the demo account's sample history covering the few weeks before
    `today`. Cheap after the first call per day per process."""
    seeded_for = current_app.extensions.setdefault("gym_demo_seeded", set())
    if today in seeded_for:
        return
    plan = current_app.extensions["gym_catalog"].active_plan
    newest = (
        db.session.query(GymSession.session_date)
        .filter(GymSession.user_id == DEMO_USER)
        .order_by(GymSession.session_date.desc())
        .limit(1)
        .scalar()
    )
    if newest is None or (today - newest).days > 7 or newest >= today:
        GymSession.query.filter_by(user_id=DEMO_USER).delete()
        db.session.commit()
        for session in _demo_sessions(plan, today):
            db.session.add(session)
        db.session.commit()
    seeded_for.add(today)


def _start_weight(text: str | None) -> Decimal:
    import re

    m = re.search(r"\d+(\.\d+)?", text or "")
    return Decimal(m.group(0)) if m else Decimal(20)


def _demo_sessions(plan, today: date):
    cat = current_app.extensions["gym_catalog"]
    first = max(plan.starts, today - timedelta(weeks=DEMO_WEEKS))
    day = first
    n = 0
    while day < today:
        code = scheduled_day(plan, day)
        if code:
            week = plan_week(plan, day) or 1
            session = GymSession(
                user_id=DEMO_USER,
                session_date=day,
                plan=plan.plan,
                day_code=code,
                finished=True,
                warmup_done=[True] * len(plan.warmup),
                rope_rounds=[True] * (plan.finisher.rounds if plan.finisher else 0),
                notes="Sample session (demo data)." if n == 0 else None,
                updated_at=datetime.combine(day, datetime.min.time()),
            )
            for item in plan.days[code]:
                key = cat.effective_key(item.key)
                load = cat.exercises[key].load
                sets = deload_sets(item.sets) if is_deload(plan, week) else item.sets
                low, high = item.reps
                for set_no in range(1, sets + 1):
                    reps = min(high, low + (week - 1) + (1 if set_no == 1 else 0))
                    weight = None
                    if load in ("db_single", "db_per_hand"):
                        weight = _start_weight(item.start) + Decimal(5 * ((week - 1) // 3))
                    session.sets.append(
                        GymSet(
                            exercise_key=key,
                            set_no=set_no,
                            weight=weight,
                            band="medium" if load == "band" else None,
                            reps=reps,
                        )
                    )
            n += 1
            yield session
        day += timedelta(days=1)
