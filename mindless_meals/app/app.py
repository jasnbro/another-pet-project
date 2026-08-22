import os

from flask import Flask, render_template, url_for

from api import api
from db import db
from models import EFFORT_LEVELS, MEAL_TYPES, Favorite, Recipe, other_tag_label
from seed import seed_recipes


def _default_database_uri():
    # In the deployed container, ./data is bind-mounted to /data (see
    # compose.yml) so the SQLite file survives container restarts. Outside
    # docker (local dev, tests, this sandbox) fall back to Flask's instance
    # folder. Either way, set DATABASE_URL to point at Postgres instead —
    # no code changes needed, since the app already speaks to it purely
    # through SQLAlchemy.
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        return "sqlite:////data/mindless_meals.db"
    instance_dir = os.path.join(os.path.dirname(__file__), "instance")
    os.makedirs(instance_dir, exist_ok=True)
    return f"sqlite:///{os.path.join(instance_dir, 'mindless_meals.db')}"


def create_app(config_overrides=None):
    """Application factory.

    A plain module-level Flask app can't be pointed at an isolated test
    database without touching real dev data, so tests (see tests/) call
    this directly with an in-memory SQLITE_DATABASE_URI override instead.
    """
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", _default_database_uri())
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SEED_ON_START"] = True
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    app.register_blueprint(api)

    @app.template_global()
    def asset_url(filename):
        """url_for('static', ...) plus a cache-busting ?v=<mtime> query
        string, so a browser holding a cached copy of e.g. mindless-
        meals.js always fetches the new one after a deploy instead of
        silently running stale JS against fresh HTML (which is exactly
        how a template change like dropping a CSS class can make every
        click handler bound to that class quietly stop attaching)."""
        path = os.path.join(app.static_folder, filename)
        try:
            version = int(os.path.getmtime(path))
        except OSError:
            version = 0
        return url_for("static", filename=filename) + f"?v={version}"

    with app.app_context():
        db.create_all()
        if app.config["SEED_ON_START"] and Recipe.query.count() == 0:
            seed_recipes()

    @app.cli.command("seed")
    def seed_command():
        """Re-run the recipe seed (adds any recipes missing from the DB)."""
        added = seed_recipes()
        print(f"Added {added} recipe(s) from seed data.")

    @app.route("/")
    def home():
        recipes = Recipe.query.order_by(Recipe.cuisine, Recipe.name).all()
        favorite_ids = {f.recipe_id for f in Favorite.query.all()}

        cuisines = sorted({r.cuisine for r in recipes})
        grouped = {c: [] for c in cuisines}
        other_tags = set()
        for r in recipes:
            grouped[r.cuisine].append(r)
            other_tags.update(r.other_tags or [])
        other_tag_options = sorted(
            ({"value": t, "label": other_tag_label(t)} for t in other_tags),
            key=lambda o: o["label"],
        )

        return render_template(
            "index.html",
            grouped_recipes=[(c, grouped[c]) for c in cuisines],
            cuisines=cuisines,
            favorite_ids=favorite_ids,
            effort_levels=EFFORT_LEVELS,
            meal_types=MEAL_TYPES,
            other_tag_options=other_tag_options,
            recipes_json=[r.to_dict() for r in recipes],
            favorite_ids_json=list(favorite_ids),
        )

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
