Mindless Meals 🐙
==================

A quiet little recipe app that answers one question: **what should I eat
this week?**

No calorie counting, no dashboards, no gamification — just a calm place
to browse recipes, build a meal plan, and get back to your day. Think
"personal field guide," not "SaaS product." It's part of the Undercurrent
family ("quiet infrastructure for everyday life"), with its own orange
identity.

---

## What it does

- **Browse & filter** — 48 recipes grouped into 13 cuisine/category
  sections (East Asian, Caribbean Inspired, Breakfast Rotation, and so
  on). Filter by Effort, meal Type, Cuisine, or Other tags
  (freezer-friendly, high-protein, etc.), or just search by name,
  ingredient, or sauce. 25 recipes show at a time, with a quiet "Show
  More" to reveal the rest — no infinite scroll, no pagination maze.
- **Favorites** — star the ones you actually make. "View Favorites"
  filters down to just those.
- **Meal planning** — tap a meal-type pill under any recipe to add it to
  a draft plan, then save it. "View Recent Plan" brings back whatever
  you saved most recently.
- **Add, edit, and delete recipes** — a friendly form with chip-style
  ingredient/sauce inputs (type and hit Enter, like adding tags) and a
  "Preview Recipe" step so you see exactly what you're about to save.
  Deleting a recipe cleans up after itself — it comes out of favorites
  and any meal plans too.
- **Recipe links** — paste in a TikTok, Reels, or blog link so you can
  always find the original.
- **Export** — download your recipes as a YAML file, either all of them,
  just your favorites, whatever's currently filtered, or a hand-picked
  selection. Doubles as a backup. You can also export your current meal
  plan as a plain text file for a grocery run.

---

## Quick start

You don't need a database server to try this out — it runs on a local
SQLite file with zero setup:

```bash
cd mindless_meals/app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
FLASK_APP=app flask run --port=8000
```

Then open **http://localhost:8000** — the app seeds itself with all 48
recipes on first run.

### Running it with Docker (and real Postgres)

If you want to run this the way it runs in production — behind Docker,
talking to a real Postgres database instead of a local file — see
**[`docs/database.md`](docs/database.md)**. Short version:

```bash
cd mindless_meals
docker compose up --build -d
docker compose logs -f   # watch it start
```

This needs a `postgres` service already running and a `.env` file with
`DATABASE_URL` set (see `.env.example`) — `docs/database.md` walks
through all of it, including the database schema, backups, and how to
run migrations.

---

## How it's built

Nothing fancy on purpose: a server-rendered page, a sprinkle of vanilla
JavaScript, and a small Flask API in front of a database. No frontend
framework, no build step.

```
Your browser
     │
     ▼
Server-rendered page + a little JS  (templates/, static/)
     │
     ▼
JSON API                            (api.py)
     │
     ▼
Database models                     (models.py)
     │
     ▼
SQLite (default) or Postgres        (whichever DATABASE_URL points at)
```

**Where things live**, if you're poking around the code:

| File | What it's for |
|---|---|
| `app.py` | Starts the Flask app, wires everything together |
| `models.py` | The database tables, as Python classes |
| `api.py` | The JSON endpoints the page's JavaScript calls |
| `seed.py` + `seed_data/recipes.yaml` | The original 48 recipes, loaded in on first run |
| `import_ingredients.py` + `seed_data/ingredients.yaml` | Builds a searchable ingredient catalog from those recipes (see [Known gaps](#known-gaps)) |
| `templates/index.html` | The one page the whole app lives on |
| `static/js/mindless-meals.js` | Wires up everything you click — filters, favorites, the recipe form, exporting |
| `static/js/filtering.js`, `static/js/recipe-form.js` | The parts of that logic that don't touch the page directly, so they can be tested on their own |
| `static/css/mindless-meals.css` | All the styling |
| `migrations/` | Database schema history, managed by a tool called Alembic (more on this below) |

Recipes you add through the app live in the database — nothing
auto-saves to a file. If you want a copy outside the database, use the
**Export** button.

---

## The database

By default, Mindless Meals runs on a plain **SQLite** file — no setup,
nothing to install. Set a `DATABASE_URL` environment variable and it
switches to **Postgres** instead, with no code changes — same app,
different storage.

Schema changes (adding a table, a column, a constraint) go through
**Alembic**, a migration tool — think of it as version control for the
database, so changes are tracked and reversible instead of just
happening.

For the full picture — every table, an entity diagram, how backups work,
and the ingredient-catalog import — see **[`docs/database.md`](docs/database.md)**.
That's also where the known rough edges around the newer database
tables are tracked in detail.

---

## Running the tests

```bash
cd mindless_meals/app
pip install -r requirements-dev.txt
pytest                      # 41 tests — the API, persistence, and seeding
node --test tests/*.test.js # 26 tests — client-side filtering and the recipe form
```

Both suites run against an isolated in-memory/temporary setup, so
there's no risk to any real data.

---

## Known gaps

Nothing below is broken — this is just an honest list of what's
unfinished, so nothing surprises you:

- **No automated testing on push/PR yet.** The test suites above have
  to be run by hand for now.
- **Meal-type tags (Breakfast/Lunch/Dinner/Snack) are a best guess**,
  not hand-verified for every recipe — the original recipe data never
  recorded this. If one looks wrong, Edit the recipe to fix it.
- **Saving a meal plan always creates a new one** — there's no "update"
  yet, and no way to browse or delete older saved plans from the app
  (only the most recent one is reachable, via "View Recent Plan").
- **Adding a recipe with a name + cuisine that already exists** currently
  fails with a generic error instead of a friendly "that recipe already
  exists" message.
- **The ingredient catalog and grocery-list tables exist in the database
  but aren't connected to the app yet** — they're there as groundwork
  for ingredient search and shopping lists, not live features. See
  `docs/database.md` for the plan.
- **If you're setting this up against Postgres for the first time**, run
  the database migrations (`alembic upgrade head`) *before* you start
  the app. Starting the app first can create tables of its own that
  Alembic then doesn't recognize, which makes migrations fail
  afterward. See `docs/database.md` for the full Postgres setup walkthrough.
- **The app runs on Flask's built-in development server**, which says
  so in its own startup warning. Fine for how this is used today; worth
  swapping for a production server (like gunicorn) if that ever
  changes.

Found something else, or want to tackle one of these? Just ask.
