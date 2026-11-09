"""Gym Log Flask app. `flask --app app run` finds create_app() here.

Startup loads and validates data/*.yaml (loader.py) and refuses to start
if it's invalid, printing every problem. Same layout and conventions as
mindless_meals/: one DATABASE_URL setting, SQLite when it's unset.
"""
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, send_from_directory, url_for

from .api import api
from .db import db
from .loader import CatalogError, load_catalog

APP_DIR = Path(__file__).resolve().parent
# Exercise illustration frames (Workout Guide). Kept outside app/ so the
# Dockerfile copies them in their own layer, which every image version shares.
FRAMES_DIR = APP_DIR.parent / "frames"
FRAMES_MAX_AGE = 30 * 24 * 3600  # frames never change within a Workout Guide version
# Matches --bg in static/css/gym-log.css (light and dark).
THEME_COLOR = "#f5f3ee"
THEME_COLOR_DARK = "#16191c"


def _default_database_uri():
    # Local dev and the CI smoke test only. Production sets DATABASE_URL.
    instance_dir = APP_DIR.parent / "instance"
    instance_dir.mkdir(exist_ok=True)
    return f"sqlite:///{instance_dir / 'gym_log.db'}"


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.json.sort_keys = False  # keep YAML file order (exercises, equipment, days)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL") or _default_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["GYM_DATA_DIR"] = os.environ.get("GYM_DATA_DIR")  # default: gym_log/data
    if config_overrides:
        app.config.update(config_overrides)

    try:
        catalog = load_catalog(app.config["GYM_DATA_DIR"])
    except CatalogError as exc:
        # Refuse to start: a half-valid plan is worse than a clear error.
        raise SystemExit(f"{exc}\nFix the YAML and restart. See gym_log/README.md.") from None
    for warning in catalog.warnings:
        print(f"Gym Log warning: {warning}", file=sys.stderr)
    app.extensions["gym_catalog"] = catalog

    db.init_app(app)
    app.register_blueprint(api)

    with app.app_context():
        # SQLite (dev/tests) only. On Postgres the schema is Alembic's job,
        # so create_all() can never create tables behind its back (see the
        # repo's AGENTS.md, first entry).
        if db.engine.url.get_backend_name() == "sqlite":
            db.create_all()

    @app.template_global()
    def asset_url(filename):
        """Static URL with ?v=<mtime>, so a deploy never runs stale JS."""
        try:
            version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
        except OSError:
            version = 0
        return url_for("static", filename=filename) + f"?v={version}"

    @app.route("/")
    def home():
        return render_template(
            "index.html",
            uc_app_name="Gym Log",
            theme_color=THEME_COLOR,
            theme_color_dark=THEME_COLOR_DARK,
        )

    @app.route("/frames/<path:filename>")
    def frames(filename):
        # send_from_directory refuses paths that escape FRAMES_DIR.
        return send_from_directory(FRAMES_DIR, filename, max_age=FRAMES_MAX_AGE)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    # Installable web app (Undercurrent web standard; shared/undercurrent-web).
    @app.route("/sw.js")
    def service_worker():
        response = send_from_directory(app.static_folder, "undercurrent/sw.js")
        response.headers["Content-Type"] = "text/javascript"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.route("/manifest.webmanifest")
    def manifest():
        def icon(name):
            return url_for("static", filename=f"img/icons/{name}")

        response = jsonify(
            {
                "name": "Gym Log",
                "short_name": "Gym Log",
                "description": "Home gym workout log.",
                "start_url": "/",
                "scope": "/",
                "display": "standalone",
                "orientation": "any",
                "background_color": THEME_COLOR,
                "theme_color": THEME_COLOR,
                "icons": [
                    {"src": icon("icon-192.png"), "sizes": "192x192", "type": "image/png"},
                    {"src": icon("icon-512.png"), "sizes": "512x512", "type": "image/png"},
                    {
                        "src": icon("icon-maskable-512.png"),
                        "sizes": "512x512",
                        "type": "image/png",
                        "purpose": "maskable",
                    },
                ],
            }
        )
        response.headers["Content-Type"] = "application/manifest+json"
        return response

    return app
