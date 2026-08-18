Mindless Meals
==============

Purpose
-------
A quiet, text-forward recipe atlas: make deciding what to eat require as
little cognitive effort as possible. Not a meal-tracking dashboard — a
personal tool, closer to a field guide than a SaaS product.

Part of the Undercurrent family ("quiet infrastructure for everyday
life"), with its own orange identity.

Architecture
------------
UI (server-rendered page + a little vanilla JS) → JSON API → database.

- `app/app.py` — Flask application factory (`create_app`), routes for
  `/`, `/health`, and the JSON API blueprint.
- `app/models.py` — SQLAlchemy models: `Recipe`, `Favorite`, `MealPlan`
  / `MealPlanItem`. Effort levels, meal types, and the known "Other"
  tag vocabulary are defined here as small constants, not separate
  tables — the vocabulary is small and single-user.
- `app/api.py` — the JSON API (`/api/recipes`, `/api/favorites`,
  `/api/meal-plans`), including Add Recipe validation.
- `app/seed.py` + `app/seed_data/recipes.yaml` — one-time-authored
  recipe data (originally extracted from an earlier static prototype),
  loaded into the DB on first run. Idempotent by name+cuisine. Recipes
  added afterwards through the app live only in the database.
- `app/templates/index.html` + `app/static/` — the page itself. No
  frontend framework; `static/js/filtering.js` holds the pure
  Effort/Type/Cuisine/Other/favorites matching logic (shared with its
  test suite), and `static/js/mindless-meals.js` wires it to the DOM
  (filter panels, favoriting, the meal-plan draft, Add Recipe).

Data
----
SQLite by default (Flask's instance folder locally, or `/data` when the
container's bind mount is present — see `compose.yml`). Point
`DATABASE_URL` at the shared Postgres service instead for a real
deployment; no code changes needed either way, since persistence goes
through SQLAlchemy.

Portion guidance (future work per the product spec) has a documented
extension point — `Recipe.portion_note` — rather than a calorie/macro
system. Simple portion guidance, not nutrition tracking.

Running locally
----------------
    cd mindless_meals/app
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    FLASK_APP=app flask run --port=8000

Or via Docker:

    cd mindless_meals
    docker compose up --build

Tests
-----
    cd mindless_meals/app
    pip install -r requirements-dev.txt
    pytest                                    # API + persistence + seeding
    node --test tests/filtering.test.js       # client-side filtering logic

Future
------
- Costco staples
- Reminders integration
