"""Postgres access: the two tables that hold what was actually done.

Every row belongs to one Undercurrent account (`user_id`, the identity
database's users.id). Rows from before accounts existed carry
`unclaimed` until the owner runs `flask gym claim <email>`; the read-only
demo's rows belong to `demo`.

Plans are NOT stored here; they live in data/plans/*.yaml. Each session
records which plan and day it used, so old logs stay meaningful after a
plan changes. Exercise keys are plain text, validated against
exercises.yaml by the API (keys are permanent, so they never dangle).

Schema changes go through Alembic (migrations/). SQLite is only for local
dev and tests, where create_all() builds the schema; the boolean[] columns
become JSON there.
"""
from datetime import date

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    SmallInteger,
    String,
    Text,
    false,
    func,
)
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _sqlite_enforce_foreign_keys(dbapi_connection, _record):
    # SQLite (dev, tests) ignores foreign keys unless asked; Postgres always
    # enforces them. Turn them on so tests fail where production would.
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

BoolArray = ARRAY(Boolean).with_variant(JSON(), "sqlite")
DEMO_USER = "demo"
UNCLAIMED = "unclaimed"


class GymSession(db.Model):
    __tablename__ = "gym_sessions"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    day_code: Mapped[str] = mapped_column(Text, nullable=False)
    finished: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    warmup_done: Mapped[list] = mapped_column(BoolArray, nullable=False, default=list)
    rope_rounds: Mapped[list] = mapped_column(BoolArray, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    sets: Mapped[list["GymSet"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="(GymSet.exercise_key, GymSet.set_no)",
        passive_deletes=True,
    )


class GymSet(db.Model):
    __tablename__ = "gym_sets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "session_date"],
            ["gym_sessions.user_id", "gym_sessions.session_date"],
            name="gym_sets_session_fkey",
            ondelete="CASCADE",
            onupdate="CASCADE",  # `flask gym claim` re-owns sessions; their sets follow
        ),
    )

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    exercise_key: Mapped[str] = mapped_column(Text, primary_key=True)
    set_no: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    weight = mapped_column(Numeric(5, 1))  # lb; null for bodyweight/seconds
    band: Mapped[str | None] = mapped_column(Text)  # band label when load = band
    reps: Mapped[int | None] = mapped_column(SmallInteger)  # or seconds when load = seconds

    session: Mapped[GymSession] = relationship(back_populates="sets")
