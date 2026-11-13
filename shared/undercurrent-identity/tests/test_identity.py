from datetime import timedelta

from sqlalchemy import select, update

from undercurrent_identity import store as st
from undercurrent_identity.testing import SoftPasskey, sign_in as quick_sign_in

from .conftest import ORIGIN, post, register, sign_in


def invite(identity, email="friend@example.com", apps=("gym_log",)):
    return identity.store.create_link("invite", email, apps)


# --- invite -> passkey -> signed in ---------------------------------------------

def test_invite_creates_account_with_grants_and_signs_in(client, identity):
    token = invite(identity)
    assert client.get(f"/auth/invite/{token}").status_code == 200
    _, r = register(client, token, display_name="Friend")
    assert r.status_code == 200, r.json
    assert "uc_session" in r.headers["Set-Cookie"] and "HttpOnly" in r.headers["Set-Cookie"]
    user = identity.store.get_user_by_email("friend@example.com")
    assert user.display_name == "Friend" and user.apps == {"gym_log"}
    assert client.get("/").json == {"user": "friend@example.com", "access": True}


def test_invite_link_is_single_use(client, identity):
    token = invite(identity)
    register(client, token)
    assert client.get(f"/auth/invite/{token}").status_code == 410
    r = post(client, "/auth/api/register/begin", {"token": token})
    assert r.status_code == 410


def test_expired_invite_is_refused(client, identity):
    token = invite(identity)
    with identity.store.engine.begin() as c:
        c.execute(update(st.links).values(expires_at=st.now() - timedelta(minutes=1)))
    assert client.get(f"/auth/invite/{token}").status_code == 410
    assert post(client, "/auth/api/register/begin", {"token": token}).status_code == 410


def test_raw_tokens_are_never_stored(client, identity):
    token = invite(identity)
    register(client, token)
    session_token = client.get_cookie("uc_session").value
    with identity.store.engine.connect() as c:
        dump = repr(c.execute(select(st.links)).all()) + repr(c.execute(select(st.sessions)).all())
    assert token not in dump and session_token not in dump


def test_invite_for_existing_account_adds_grant_and_passkey(client, identity):
    register(client, invite(identity))
    register(client, invite(identity, apps=("mindless_meals",)))
    user = identity.store.get_user_by_email("friend@example.com")
    assert user.apps == {"gym_log", "mindless_meals"}
    assert len(identity.store.list_users()) == 1
    assert len(identity.store.passkeys_for(user.id)) == 2


def test_user_handle_is_the_account_id(client, identity):
    passkey, _ = register(client, invite(identity))
    user = identity.store.get_user_by_email("friend@example.com")
    assert passkey.user_handle.decode() == user.id


# --- signing in ------------------------------------------------------------------------

def test_passkey_sign_in(client, identity, app):
    passkey, _ = register(client, invite(identity))
    fresh = app.test_client()
    r = sign_in(fresh, passkey)
    assert r.status_code == 200 and r.json["next"] == "/"
    assert fresh.get("/").json["user"] == "friend@example.com"
    # sign count advanced and stored
    row = identity.store.get_passkey(identity.store.passkeys_for(identity.store.get_user_by_email("friend@example.com").id)[0].credential_id)
    assert row.sign_count == passkey.sign_count and row.last_used_at is not None


def test_unknown_passkey_is_refused(client):
    assert sign_in(client, SoftPasskey()).status_code == 401


def test_challenge_is_single_use(client, identity):
    passkey, _ = register(client, invite(identity))
    begin = post(client, "/auth/api/sign-in/begin")
    cred = passkey.get(begin.json["options"])
    body = {"challenge_id": begin.json["challenge_id"], "credential": cred}
    assert post(client, "/auth/api/sign-in/finish", body).status_code == 200
    assert post(client, "/auth/api/sign-in/finish", body).status_code == 400


def test_signature_from_wrong_origin_fails(client, identity, app):
    passkey, _ = register(client, invite(identity))
    fresh = app.test_client()
    begin = post(fresh, "/auth/api/sign-in/begin")
    cred = passkey.get(begin.json["options"], origin="http://evil.example")
    r = post(fresh, "/auth/api/sign-in/finish", {"challenge_id": begin.json["challenge_id"], "credential": cred})
    assert r.status_code == 401


def test_disabled_account_cannot_sign_in_and_is_signed_out(client, identity, app):
    passkey, _ = register(client, invite(identity))
    user = identity.store.get_user_by_email("friend@example.com")
    identity.store.set_disabled(user.id, True)
    assert client.get("/").json["user"] is None  # existing session ended
    assert sign_in(app.test_client(), passkey).status_code == 403


def test_safe_next_only_allows_local_paths(client, identity, app):
    passkey, _ = register(client, invite(identity))
    for bad in ("https://evil.example", "//evil.example", "/\\evil.example"):
        fresh = app.test_client()
        begin = post(fresh, "/auth/api/sign-in/begin")
        cred = passkey.get(begin.json["options"])
        r = post(fresh, "/auth/api/sign-in/finish", {"challenge_id": begin.json["challenge_id"], "credential": cred, "next": bad})
        assert r.json["next"] == "/"


# --- recovery ----------------------------------------------------------------------------

def test_recovery_link_adds_a_passkey_to_the_same_account(client, identity, app):
    old, _ = register(client, invite(identity))
    token = identity.store.create_link("recovery", "friend@example.com")
    other = app.test_client()
    assert other.get(f"/auth/recover/{token}").status_code == 200
    assert other.get(f"/auth/invite/{token}").status_code == 410  # wrong kind
    new, r = register(other, token)
    assert r.status_code == 200
    user = identity.store.get_user_by_email("friend@example.com")
    assert len(identity.store.passkeys_for(user.id)) == 2
    assert sign_in(app.test_client(), old).status_code == 200  # old one still works
    assert sign_in(app.test_client(), new).status_code == 200


# --- access rules ----------------------------------------------------------------------------

def test_require_access(client, identity, app):
    assert client.get("/api/private").status_code == 401
    register(client, invite(identity, apps=("mindless_meals",)))
    assert client.get("/api/private").status_code == 403  # signed in, no grant for gym_log
    identity.store.grant(identity.store.get_user_by_email("friend@example.com").id, "gym_log")
    assert client.get("/api/private").json == {"user": "friend@example.com"}


def test_quick_sign_in_helper(client, identity):
    quick_sign_in(client, identity, "owner@example.com")
    assert client.get("/api/private").json == {"user": "owner@example.com"}


# --- CSRF: every POST needs an allowed Origin -------------------------------------------------

def test_posts_without_or_from_foreign_origin_are_refused(client):
    assert post(client, "/auth/api/sign-in/begin", origin=None).status_code == 403
    assert post(client, "/auth/api/sign-in/begin", origin="https://evil.example").status_code == 403
    assert post(client, "/auth/api/sign-in/begin", origin=ORIGIN).status_code == 200


def test_production_origins(identity):
    identity.rp_id = "undercurrentlabs.dev"
    ok = ["https://undercurrentlabs.dev", "https://gym.undercurrentlabs.dev", "https://meals.undercurrentlabs.dev"]
    bad = ["http://gym.undercurrentlabs.dev", "https://undercurrentlabs.dev.evil.example", "https://evilundercurrentlabs.dev", None]
    assert all(identity.allowed_origin(o) for o in ok)
    assert not any(identity.allowed_origin(o) for o in bad)


# --- sessions ------------------------------------------------------------------------------------

def test_sign_out_and_sign_out_everywhere(client, identity, app):
    passkey, _ = register(client, invite(identity))
    phone = app.test_client()
    sign_in(phone, passkey)
    r = client.post("/auth/sign-out", data={"next": "/"}, headers={"Origin": ORIGIN})
    assert r.status_code == 302 and "uc_session=;" in r.headers["Set-Cookie"]
    assert client.get("/").json["user"] is None
    assert phone.get("/").json["user"] == "friend@example.com"  # other device unaffected
    phone.post("/auth/sign-out", data={"everywhere": "1"}, headers={"Origin": ORIGIN})
    assert identity.store.end_all_sessions(identity.store.get_user_by_email("friend@example.com").id) == 0


def test_expired_session_is_ignored(client, identity):
    register(client, invite(identity))
    with identity.store.engine.begin() as c:
        c.execute(update(st.sessions).values(expires_at=st.now() - timedelta(seconds=1)))
    assert client.get("/").json["user"] is None


def test_cookie_domain_and_secure_in_production(tmp_path):
    from flask import Flask
    from undercurrent_identity import Identity

    app = Flask(__name__, instance_path=str(tmp_path / "i"))
    app.config.update(IDENTITY_DATABASE_URL=f"sqlite:///{tmp_path / 'p.db'}", IDENTITY_RP_ID="undercurrentlabs.dev",
                      IDENTITY_COOKIE_DOMAIN=".undercurrentlabs.dev")
    identity = Identity(app, app_name="gym_log")
    with app.test_request_context():
        from flask import make_response
        r = make_response("")
        identity.set_session_cookie(r, "t")
    cookie = r.headers["Set-Cookie"]
    for part in ("Domain=undercurrentlabs.dev", "Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
        assert part in cookie, cookie


# --- passkeys on the account page ----------------------------------------------------------------

def test_add_and_remove_passkeys(client, identity):
    register(client, invite(identity))
    assert client.get("/auth/account").status_code == 200
    second, r = register(client)  # signed in: no token needed
    assert r.status_code == 200 and r.json["next"] == "/auth/account"
    user = identity.store.get_user_by_email("friend@example.com")
    keys = identity.store.passkeys_for(user.id)
    assert len(keys) == 2
    assert post(client, "/auth/api/passkeys/delete", {"credential_id": keys[0].credential_id}).status_code == 200
    only = identity.store.passkeys_for(user.id)[0].credential_id
    assert post(client, "/auth/api/passkeys/delete", {"credential_id": only}).status_code == 400


def test_signed_out_cannot_add_passkey(client):
    assert post(client, "/auth/api/register/begin", {}).status_code == 401


def test_two_devices_racing_on_one_invite_only_one_wins(client, identity, app):
    """Both start before either finishes: the link is consumed inside the
    finishing transaction, so the second finish must fail."""
    token = invite(identity)
    other = app.test_client()
    a, b = SoftPasskey(), SoftPasskey()
    begin_a = post(client, "/auth/api/register/begin", {"token": token})
    begin_b = post(other, "/auth/api/register/begin", {"token": token})
    finish = lambda c, begin, pk: post(c, "/auth/api/register/finish", {  # noqa: E731
        "challenge_id": begin.json["challenge_id"], "credential": pk.create(begin.json["options"])})
    assert finish(client, begin_a, a).status_code == 200
    r = finish(other, begin_b, b)
    assert r.status_code == 410 and "already been used" in r.json["error"]
    assert len(identity.store.passkeys_for(identity.store.get_user_by_email("friend@example.com").id)) == 1


def test_pages_use_friendly_app_names(client, identity):
    token = identity.store.create_link("invite", "friend@example.com", ["gym_log", "mindless_meals"])
    html = client.get(f"/auth/invite/{token}").get_data(as_text=True)
    assert "Gym Log, Mindless Meals" in html and "gym_log" not in html
    register(client, token)
    assert "Gym Log, Mindless Meals" in client.get("/auth/account").get_data(as_text=True)
