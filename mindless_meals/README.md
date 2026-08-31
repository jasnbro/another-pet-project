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
  and Edit, restaurant-style: Ingredients/Sauce are tokenized chip
  inputs (type, then Enter/comma/blur to commit a chip — multiword
  entries like "purple cabbage" stay together; Backspace on an empty
  entry selects, then removes, the last chip), and Make is a short
  arrow-joined action sequence ("Roast sweet potatoes → Brown turkey →
  Assemble bowls"), not a numbered method — typed with newlines,
  commas, semicolons, or arrows and normalized either way. Both submit
  to **Preview Recipe** first, showing the recipe in its actual card
  presentation with Save Recipe / Back to Edit / Cancel — nothing is
  written until Save is clicked. Deleting a recipe also removes it from
  favorites and any saved meal plans (and removes a plan entirely if
  that empties it).
- **Recipe links** — an optional URL field for wherever a recipe
  actually came from (a TikTok/Reels video, a recipe site), shown on
  the card when present.
- **Export** — one dialog, five scopes: All recipes, Favorites,
  Filtered results (honors the page's current filters/search),
  Selected recipes (a checkbox selection mode on the recipe list —
  Select all shown / Clear selection / Export selected / Cancel — kept
  separate from the meal-plan slot pills), and Current meal plan
  (readable, grouped by slot). Each option shows how many recipes/plan
  entries it covers and disables itself when there's nothing to export.
  Recipe exports reuse the same YAML shape the seed loader reads, so
  "All recipes" still doubles as a restore path.

Architecture
------------
UI (server-rendered page + a little vanilla JS) → JSON API → database.

- `app/app.py` — Flask application factory (`create_app`), routes for
  `/`, `/health`, and the JSON API blueprint.
- `app/models.py` — SQLAlchemy models: `Recipe`, `Favorite`, `MealPlan`
  / `MealPlanItem`. Effort levels, meal types, and the known "Other"
  tag vocabulary are defined here as small constants, not separate
  tables — the vocabulary is small and single-user.
- `app/api.py` — the JSON API: `GET/POST /api/recipes`,
  `PUT/DELETE /api/recipes/<id>`, `GET /api/recipes/export` (optional
  `?ids=1,2,3` scopes it to specific recipes — Favorites/Filtered
  results/Selected recipes all reuse this one endpoint),
  `GET/POST/DELETE /api/favorites[/<id>]`,
  `GET /api/meal-plans/current`, `POST /api/meal-plans`,
  `GET /api/meal-plans/current/export` (plain text, grouped by slot).
  Add and Edit share one validation function, which also normalizes
  Make's separators server-side as a safety net for direct API calls.
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
  Effort/Type/Cuisine/Other/favorites/search matching logic and
  `static/js/format.js` the pure chip-list/Make-arrow normalization
  logic (each shared with its own test suite, same split), used by
  `static/js/chip-input.js` (the Ingredients/Sauce chip widget — DOM
  wiring only, keeps a hidden field in sync with the same "A · B · C"
  string the backend has always stored) and `static/js/mindless-
  meals.js`, which wires everything to the DOM: filter panels,
  favoriting, the meal-plan draft, export-selection mode, and the
  Add/Edit/Delete Recipe dialog (Edit pre-fills from the recipe's own
  data, already embedded in the page; Preview Recipe builds a card
  matching the real presentation before Save submits a `PUT`/`POST`).

Data
----
SQLite by default (Flask's instance folder locally, or `/data` when the
container's bind mount is present — see `compose.yml`). Point
`DATABASE_URL` at the shared Postgres service instead for a real
deployment; no code changes needed either way, since persistence goes
through SQLAlchemy.

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
    pytest                                              # 42 tests: API, persistence, seeding, Make normalization, export scopes
    node --test tests/filtering.test.js tests/format.test.js   # 27 tests: client-side filtering + chip/Make formatting logic

Known gaps
----------
- No CI workflow — the test suites above aren't run automatically on
  push/PR yet.
- No automated browser test suite — the chip inputs, preview flow, and
  export dialog are covered by pytest (server behavior) and format.js's
  node tests (pure formatting logic), but the actual DOM
  wiring/interactions were verified by hand (a Playwright run during
  development, not a committed test) rather than an automated browser
  test that runs alongside the rest of the suite.
- Meal-type assignments on the 48 seed recipes are a heuristic (section
  → meal type), not recipe-by-recipe ground truth, since the original
  data never recorded this. One clear mismatch ("Breakfast Burritos")
  has been corrected; anything else that's wrong is fixable via Edit.
- Portion guidance has a model field but no UI yet.
