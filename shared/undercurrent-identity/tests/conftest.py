import pytest
from flask import Flask, jsonify

from undercurrent_identity import Identity
from undercurrent_identity.testing import SoftPasskey

ORIGIN = "http://localhost"


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path / "instance"))
    app.config.update(TESTING=True, IDENTITY_DATABASE_URL=f"sqlite:///{tmp_path / 'identity.db'}")
    identity = Identity(app, app_name="gym_log")

    @app.get("/api/private")
    @identity.require_access
    def private():
        return jsonify({"user": identity.current_user().email})

    @app.get("/")
    def home():
        user = identity.current_user()
        return {"user": user.email if user else None, "access": identity.has_access()}

    return app


@pytest.fixture
def identity(app):
    return app.extensions["undercurrent_identity"]


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, path, body=None, origin=ORIGIN):
    headers = {"Origin": origin} if origin else {}
    return client.post(path, json=body or {}, headers=headers)


def register(client, token=None, passkey=None, display_name=None, origin=ORIGIN):
    passkey = passkey or SoftPasskey()
    begin = post(client, "/auth/api/register/begin", {"token": token, "display_name": display_name}, origin)
    assert begin.status_code == 200, begin.json
    cred = passkey.create(begin.json["options"], origin=origin)
    finish = post(client, "/auth/api/register/finish", {"challenge_id": begin.json["challenge_id"], "credential": cred}, origin)
    return passkey, finish


def sign_in(client, passkey, origin=ORIGIN):
    begin = post(client, "/auth/api/sign-in/begin", origin=origin)
    assert begin.status_code == 200
    cred = passkey.get(begin.json["options"], origin=origin)
    return post(client, "/auth/api/sign-in/finish", {"challenge_id": begin.json["challenge_id"], "credential": cred}, origin)
