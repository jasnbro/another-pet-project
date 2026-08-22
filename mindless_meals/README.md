Mindless Meals
==============

Purpose
-------
A quiet, text-forward recipe atlas: make deciding what to eat require as
little cognitive effort as possible. Not a meal-tracking dashboard — a
personal tool, closer to a field guide than a SaaS product.

Part of the Undercurrent family ("quiet infrastructure for everyday
life"), with its own orange identity.

Features
--------
- **Browse & filter** — 48 seed recipes grouped by cuisine/category (13
  groupings), filterable by Effort, meal Type, Cuisine, and Other
  (freezer-friendly, high-protein, etc.), plus a plain-text search
  across name, ingredients, and sauce. Filters combine as AND across
  groups, OR within a group. 25 recipe cards are revealed at a time
  (Show More reveals another 25, purely client-side — every recipe is
  already in the page's embedded JSON, so this costs no extra request);
  narrowing search/filters resets back to the first 25 of the new set.
- **Favorites** — persisted star toggle per recipe; View Favorites shows
  only those.
- **Meal planning** — tap a recipe's applicable meal-type pill to add it
  to a draft plan, then Save Meal Plan; View Recent Plan reopens the
  most recently saved one.
- **Add / Edit / Delete recipes** — one dialog and form serve both Add
  and Edit. Deleting a recipe also removes it from favorites and any
  saved meal plans (and removes a plan entirely if that empties it).
- **Recipe links** — an optional URL field for wherever a recipe
  actually came from (a TikTok/Reels video, a recipe site), shown on
  the card when present.
- **Export / backup** — downloads every recipe as YAML in the same
  shape the seed loader reads, so it doubles as a restore path.

Architecture
------------
UI (server-rendered page + a little vanilla JS) → JSON API → database.

- `app/app.py` — Flask application factory (`create_app`), routes for
  `/`, `/health`, and the JSON API blueprint.
- `app/models.py` — SQLAlchemy models: `Recipe`, `Favorite`, `MealPlan`
  / `MealPlanItem`, plus `Ingredient` / `RecipeIngredient` and the
  forward-looking `User` / `UserPreference` / `GroceryList` /
  `GroceryListItem` (schema only — not wired into the API/UI yet). Effort
  levels, meal types, and the known "Other" tag vocabulary are defined
  here as small constants, not separate tables — the vocabulary is small
  and single-user. See `docs/database.md` for the full schema, ERD, and
  migration workflow.
- `app/api.py` — the JSON API: `GET/POST /api/recipes`,
  `PUT/DELETE /api/recipes/<id>`, `GET /api/recipes/export`,
  `GET/POST/DELETE /api/favorites[/<id>]`,
  `GET /api/meal-plans/current`, `POST /api/meal-plans`. Add and Edit
  share one validation function.
- `app/seed.py` + `app/seed_data/recipes.yaml` — one-time-authored
  recipe data (originally extracted from an earlier static prototype),
  loaded into the DB on first run. Idempotent by name+cuisine — a
  fresh/empty recipes table picks up any fix made to this file, but an
  already-seeded DB does not; use Edit (or Export Recipes, then
  reload from the export) to correct an individual row already in the
  database. Recipes added afterwards through the app live only in the
  database — back them up with Export Recipes.
- `app/templates/index.html` + `app/static/` — the page itself. No
  frontend framework; `static/js/filtering.js` holds the pure
  Effort/Type/Cuisine/Other/favorites/search matching logic (shared
  with its test suite), and `static/js/mindless-meals.js` wires it to
  the DOM (filter panels, favoriting, the meal-plan draft, and the
  Add/Edit/Delete Recipe dialog — Edit pre-fills from the recipe's own
  data, already embedded in the page, and submits a `PUT` instead of
  a `POST`).

Data
----
SQLite by default (Flask's instance folder locally, or `/data` when the
container's bind mount is present — see `compose.yml`). Point
`DATABASE_URL` at the shared Postgres service instead for a real
deployment; no code changes needed either way, since persistence goes
through SQLAlchemy. Schema changes for Postgres go through Alembic
migrations (`app/migrations/`) rather than one big schema file — see
`docs/database.md` for the full setup, ERD, and how to import the
existing recipes into the normalized ingredient list
(`flask import-ingredients`).

Of the 48 seed recipes: 9 are `easiest`, 35 `easy`, 4 `moderate`, and
none yet `more_effort` — that tier exists in the model and Add/Edit
form but nothing in the seed data uses it.

Portion guidance (future work per the product spec) has a documented
extension point — `Recipe.portion_note` — rather than a calorie/macro
system. Simple portion guidance, not nutrition tracking. Not yet
surfaced in the UI.

Running locally
----------------
    cd mindless_meals/app
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    FLASK_APP=app flask run --port=8000

Or via Docker:

    cd mindless_meals
    docker compose up --build

(The Docker build itself hasn't been verified from this codebase's
development environment, which has no docker daemon — the local venv
run above exercises the same install + run steps the container uses.)

Tests
-----
    cd mindless_meals/app
    pip install -r requirements-dev.txt
    pytest                                    # 30 tests: API, persistence, seeding
    node --test tests/filtering.test.js       # 10 tests: client-side filtering logic

Known gaps
----------
- No CI workflow — the test suites above aren't run automatically on
  push/PR yet.
- Meal-type assignments on the 48 seed recipes are a heuristic (section
  → meal type), not recipe-by-recipe ground truth, since the original
  data never recorded this. One clear mismatch ("Breakfast Burritos")
  has been corrected; anything else that's wrong is fixable via Edit.
- Portion guidance has a model field but no UI yet.
- The normalized ingredient list (`Ingredient`/`RecipeIngredient`) and
  the forward-looking `User`/`UserPreference`/`GroceryList` tables exist
  in the schema but aren't wired into `api.py` or the UI yet — see
  `docs/database.md#known-gaps--deferred-work`.
