import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from app import create_app
from app.db import db
from app.undercurrent_identity.testing import sign_in

DATA = Path(__file__).resolve().parents[1] / "data"


class DataDir:
    """A scratch copy of gym_log/data that a test can edit."""

    def __init__(self, path: Path):
        self.path = path

    def load(self, name):
        return yaml.safe_load((self.path / name).read_text(encoding="utf-8"))

    def save(self, name, value):
        (self.path / name).write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def edit(self, name, fn):
        value = self.load(name)
        fn(value)
        self.save(name, value)

    def write(self, name, text):
        (self.path / name).write_text(text, encoding="utf-8")

    def own_everything(self):
        self.edit("equipment.yaml", lambda eq: [v.update(status="owned") for v in eq.values()])


@pytest.fixture
def data_dir(tmp_path):
    shutil.copytree(DATA, tmp_path / "data")
    return DataDir(tmp_path / "data")


@pytest.fixture
def make_app(data_dir, tmp_path):
    apps = []

    def _make():
        app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "GYM_DATA_DIR": str(data_dir.path),
                "IDENTITY_DATABASE_URL": f"sqlite:///{tmp_path / f'identity{len(apps)}.db'}",
                "TESTING": True,
            }
        )
        apps.append(app)
        return app

    yield _make
    for app in apps:
        with app.app_context():
            db.session.remove()
            db.drop_all()


def owner_client(app):
    client = app.test_client()
    sign_in(client, app.extensions["undercurrent_identity"], "owner@example.com")
    return client


@pytest.fixture
def client(make_app, data_dir):
    """Signed in as the owner, with access to Gym Log."""
    data_dir.own_everything()
    app = make_app()
    client = app.test_client()
    sign_in(client, app.extensions["undercurrent_identity"], "owner@example.com")
    return client


@pytest.fixture
def anon(make_app, data_dir):
    """Signed out: sees the read-only demo."""
    data_dir.own_everything()
    return make_app().test_client()
