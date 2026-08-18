"""Having this file at the app root (rather than only under tests/) makes
pytest add mindless_meals/app itself to sys.path, so test modules can do
plain `from app import create_app` / `from db import db` regardless of
which subdirectory they live in — matching how the app's own modules
import each other (flat, no package prefix).
"""
import pytest

from app import create_app
from db import db


@pytest.fixture
def app_instance():
    """A fresh app wired to an isolated in-memory database, unseeded."""
    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SEED_ON_START": False,
            "TESTING": True,
        }
    )
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()
