"""Undercurrent accounts in Gym Log: your data when signed in with access,
a read-only demo for everyone else, and claiming pre-account history."""
import subprocess
from pathlib import Path

from app.db import UNCLAIMED, GymSession, GymSet, db
from app.undercurrent_identity.testing import create_user, sign_in

from .conftest import owner_client

PUT = "/api/gym/sessions/"
SYNC = Path(__file__).resolve().parents[2] / "shared" / "undercurrent-identity" / "sync.sh"


def put(client, day, key="goblet", weight=25, reps=12, code="A"):
    return client.put(PUT + day, json={"day_code": code, "sets": [
        {"exercise_key": key, "set_no": 1, "weight": weight, "reps": reps}]})


def test_signed_out_sees_the_read_only_demo(anon):
    me = anon.get("/api/gym/me").json
    assert me["demo"] and not me["signed_in"] and not me["can_write"]
    t = anon.get("/api/gym/today?date=2026-11-13").json
    assert t["items"][0]["last"]["date"] == "2026-11-09"  # demo history
    assert len(anon.get("/api/gym/sessions").json) >= 2
    r = put(anon, "2026-11-13")
    assert r.status_code == 401 and "Sign in" in r.json["error"]


def test_demo_is_not_owner_data_and_owner_is_not_demo(make_app, data_dir):
    data_dir.own_everything()
    app = make_app()
    owner, visitor = owner_client(app), app.test_client()
    assert owner.get("/api/gym/sessions").json == []  # owner starts empty, no demo rows
    put(owner, "2026-11-11", weight=99)
    demo = visitor.get("/api/gym/sessions").json
    assert all(s["date"] != "2026-11-11" or all(x["weight"] != 99 for x in s["sets"]) for s in demo)
    assert "99" not in visitor.get("/api/gym/export.csv").data.decode()


def test_accounts_only_see_their_own_sessions(make_app, data_dir):
    data_dir.own_everything()
    app = make_app()
    ident = app.extensions["undercurrent_identity"]
    a, b = app.test_client(), app.test_client()
    sign_in(a, ident, "a@example.com")
    sign_in(b, ident, "b@example.com")
    assert put(a, "2026-11-09", weight=30).status_code == 200
    assert put(b, "2026-11-09", weight=15).status_code == 200  # same date, separate rows
    assert [s["sets"][0]["weight"] for s in a.get("/api/gym/sessions").json] == [30]
    assert [s["sets"][0]["weight"] for s in b.get("/api/gym/sessions").json] == [15]
    assert b.get("/api/gym/today?date=2026-11-13").json["items"][0]["last"]["sets"][0]["weight"] == 15
    assert [p["weight"] for p in b.get("/api/gym/progress/goblet").json] == [15]
    assert ",30," not in b.get("/api/gym/export.csv").data.decode()


def test_account_without_the_grant_gets_the_demo_read_only(make_app, data_dir):
    data_dir.own_everything()
    app = make_app()
    c = app.test_client()
    sign_in(c, app.extensions["undercurrent_identity"], "meals-only@example.com", apps=("mindless_meals",))
    me = c.get("/api/gym/me").json
    assert me["signed_in"] and me["demo"] and not me["can_write"]
    r = put(c, "2026-11-13")
    assert r.status_code == 403 and "doesn't have access" in r.json["error"]


def test_claim_moves_pre_account_history_to_the_owner(make_app, data_dir):
    data_dir.own_everything()
    app = make_app()
    with app.app_context():
        from datetime import date
        s = GymSession(user_id=UNCLAIMED, session_date=date(2026, 11, 9), plan="home-gym-v1", day_code="A")
        s.sets.append(GymSet(exercise_key="goblet", set_no=1, weight=25, reps=12))
        db.session.add(s)
        db.session.commit()
    ident = app.extensions["undercurrent_identity"]
    runner = app.test_cli_runner()
    r = runner.invoke(args=["gym", "claim", "owner@example.com"])
    assert r.exit_code != 0 and "No Undercurrent account" in r.output
    create_user(ident, "owner@example.com", ["gym_log"])
    r = runner.invoke(args=["gym", "claim", "owner@example.com"])
    assert r.exit_code == 0 and "Moved 1 session(s) and 1 set(s)" in r.output
    owner = owner_client(app)
    sessions = owner.get("/api/gym/sessions").json
    assert [s["date"] for s in sessions] == ["2026-11-09"]
    assert [x["weight"] for x in sessions[0]["sets"]] == [25]  # sets moved with their session


def test_claim_refuses_when_dates_clash(make_app, data_dir):
    from datetime import date

    data_dir.own_everything()
    app = make_app()
    owner = owner_client(app)
    put(owner, "2026-11-09", weight=40)
    with app.app_context():
        db.session.add(GymSession(user_id=UNCLAIMED, session_date=date(2026, 11, 9), plan="home-gym-v1", day_code="A"))
        db.session.commit()
    r = app.test_cli_runner().invoke(args=["gym", "claim", "owner@example.com"])
    assert r.exit_code != 0 and "2026-11-09" in r.output and "nothing was moved" in r.output


def test_sqlite_enforces_foreign_keys_like_postgres(make_app):
    import pytest
    from datetime import date
    from sqlalchemy.exc import IntegrityError

    app = make_app()
    with app.app_context():
        db.session.add(GymSet(user_id="nobody", session_date=date(2026, 11, 9), exercise_key="goblet", set_no=1))
        with pytest.raises(IntegrityError):
            db.session.commit()


def test_sign_in_pages_are_served(anon):
    assert anon.get("/auth/sign-in").status_code == 200
    assert anon.get("/auth/account").status_code == 302


def test_identity_copy_is_up_to_date():
    if not SYNC.exists():  # not in a full checkout (e.g. inside the image)
        return
    r = subprocess.run([str(SYNC), "--check", "gym_log"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
