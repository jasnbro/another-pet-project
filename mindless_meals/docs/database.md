# Mindless Meals — Database

Mindless Meals persists everything through SQLAlchemy, so the same code
runs against either SQLite (the local/default fallback -- see `app.py`)
or PostgreSQL (the shared Atlas deployment) depending on `DATABASE_URL`.
This document covers the PostgreSQL side: schema, migrations, the
recipe/ingredient import, backups, and how it fits into the Atlas
deployment.

- [Architecture](#architecture)
- [Schema](#schema)
- [ERD](#erd)
- [Environment variables](#environment-variables)
- [Local startup](#local-startup)
- [Database initialization](#database-initialization)
- [Migrations](#migrations)
- [Importing existing recipe data](#importing-existing-recipe-data)
- [Backups](#backups)
- [Restoring a backup](#restoring-a-backup)
- [Verification steps](#verification-steps)
- [Atlas deployment](#atlas-deployment)
- [Known gaps / deferred work](#known-gaps--deferred-work)

## Architecture

```
UI (server-rendered page + vanilla JS)
        |
        v
  JSON API (api.py)
        |
        v
  SQLAlchemy models (models.py)
        |
        v
  DATABASE_URL  --unset-->  SQLite file (./data or Flask instance folder)
                --set---->  PostgreSQL (shared "postgres" service on Atlas)
```

Postgres is a **shared server** on Atlas (see the repo root `README.md`
and `postgres/compose.yml`) -- "one database per application", not one
Postgres instance per app. Mindless Meals gets its own role and database
on that shared server (see [Database
initialization](#database-initialization)); it does not use the
`postgres` superuser role directly.

## Schema

Ten tables, in three groups:

**Existing app data** (already live today, on SQLite):
- `recipes` -- one row per recipe. `ingredients` and `sauce` are still the
  free-text fields the app has always used (`·`-separated, e.g. `"Ground
  turkey · broccoli · edamame · rice"`) -- **not removed or replaced**.
  They remain the source of truth for what a recipe displays.
- `favorites` -- a starred recipe (one row per favorited recipe).
- `meal_plans` / `meal_plan_items` -- a saved draft meal plan and the
  recipes/slots in it.

**New: normalized ingredient list** (additive, not yet wired into the
UI/API):
- `ingredients` -- a catalog of raw ingredient names (no quantity or
  unit -- see [below](#why-no-quantityunit)), each with an optional
  `group` (`meat`, `seafood`, `dairy`, `egg`, `vegetable`, `fruit`,
  `grain`, `legume`, `pantry`, `other`) and `nutrition_type` (`protein`,
  `carb`, `fat`, `fiber`, `other`), plus an `aliases` list for a handful
  of entries that stand in for a choice between specific items (e.g.
  `"Ground Meat (Any)"` aliases `["ground turkey", "ground beef", "ground
  chicken"]`, so a future ingredient search for "beef" still finds
  recipes written as "ground turkey/beef"). Both `group` and
  `nutrition_type` are nullable: a newly-seen ingredient is added
  unclassified rather than guessed at or rejected.
- `recipe_ingredients` -- which recipes use which ingredients (a plain
  join table, `unique(recipe_id, ingredient_id)`).

Populated from `recipes.ingredients`/`recipes.sauce` by
`flask import-ingredients` -- see [Importing existing recipe
data](#importing-existing-recipe-data). `recipes.ingredients`/`.sauce`
are not modified by this; this is a derived, additive view on top of
them, for future ingredient search and grocery-list generation.

#### Why no quantity/unit?

By explicit product decision: this is a raw ingredient *list* ("uses
carrots"), not a recipe scaler or nutrition calculator. The original
recipe text never recorded quantities either, so adding quantity/unit
columns now would mean inventing data, not migrating it.

**New: forward-looking, not wired in yet**:
- `users` -- deliberately minimal (name + optional email). No
  password/auth fields -- authentication is genuinely out of scope here;
  designing it speculatively would be exactly the kind of premature
  schema this project is trying to avoid. `favorites` and `meal_plans` do
  **not** get a `user_id` yet, either -- they stay implicitly
  household-shared until there's a real login flow to attach them to
  (see [Known gaps](#known-gaps--deferred-work)).
- `user_preferences` -- one row per user: `dietary_restrictions` (a tag
  list, e.g. `["vegetarian", "dairy-free"]`), `default_effort_max`
  (reuses the existing effort scale), `notes`. Kept intentionally small;
  extend with real columns as real preference features arrive rather
  than an open-ended JSON blob.
- `grocery_lists` / `grocery_list_items` -- a shopping list, optionally
  generated from a `meal_plan_id`. Each item is either a catalog
  `ingredient_id` (derived from a recipe) or a freeform `custom_text`
  entry (e.g. "paper towels") -- never neither, enforced by a `CHECK`
  constraint.

### Constraints worth knowing about

- `recipes`: `UNIQUE(name, cuisine)` -- promotes the app's existing
  seed-time dedup rule (`seed.py` already treats name+cuisine as a
  recipe's identity) into a real database constraint. **Behavior change**:
  creating or editing a recipe to a name+cuisine that already exists now
  fails at the database level instead of silently succeeding, and `api.py`
  does not yet translate that into a friendly validation message -- see
  [Known gaps](#known-gaps--deferred-work).
- `ingredients.name` -- unique.
- `ingredients.group` / `.nutrition_type` -- `CHECK`-constrained to the
  fixed vocabularies above (or `NULL`).
- `recipe_ingredients` -- `UNIQUE(recipe_id, ingredient_id)`; both FKs
  `ON DELETE CASCADE`.
- `grocery_list_items` -- `CHECK(ingredient_id IS NOT NULL OR custom_text
  IS NOT NULL)`.
- Foreign keys generally use `ON DELETE CASCADE` (recipe_ingredients,
  user_preferences, grocery_list_items→grocery_list) or `ON DELETE SET
  NULL` where the parent is optional context rather than a strict owner
  (grocery_lists→meal_plan, grocery_lists→user, grocery_list_items→
  ingredient).
- Indexes beyond primary/unique/FK: `recipes.cuisine` (the home page
  groups every recipe by cuisine on every load), `meal_plans.created_at`
  (finding "the most recent plan"), `meal_plan_items.meal_plan_id`,
  `recipe_ingredients.recipe_id`/`.ingredient_id`,
  `grocery_list_items.grocery_list_id`.

## ERD

```mermaid
erDiagram
    RECIPES ||--o| FAVORITES : "favorited as"
    RECIPES ||--o{ MEAL_PLAN_ITEMS : "appears in"
    MEAL_PLANS ||--o{ MEAL_PLAN_ITEMS : contains
    RECIPES ||--o{ RECIPE_INGREDIENTS : uses
    INGREDIENTS ||--o{ RECIPE_INGREDIENTS : "used by"
    USERS ||--o| USER_PREFERENCES : has
    USERS ||--o{ GROCERY_LISTS : creates
    MEAL_PLANS ||--o{ GROCERY_LISTS : "generates (optional)"
    GROCERY_LISTS ||--o{ GROCERY_LIST_ITEMS : contains
    INGREDIENTS ||--o{ GROCERY_LIST_ITEMS : "derived from (optional)"

    RECIPES {
        int id PK
        string name
        string cuisine
        string effort
        text ingredients "legacy free text, source of truth"
        text sauce "legacy free text"
        text method
        json meal_types
        json other_tags
        string source_url
        string source "seed | user"
        datetime created_at
    }
    FAVORITES {
        int id PK
        int recipe_id FK
        datetime created_at
    }
    MEAL_PLANS {
        int id PK
        string name
        datetime created_at
    }
    MEAL_PLAN_ITEMS {
        int id PK
        int meal_plan_id FK
        int recipe_id FK
        string slot
    }
    INGREDIENTS {
        int id PK
        string name UK
        string group "nullable, fixed vocabulary"
        string nutrition_type "nullable, fixed vocabulary"
        json aliases
    }
    RECIPE_INGREDIENTS {
        int id PK
        int recipe_id FK
        int ingredient_id FK
    }
    USERS {
        int id PK
        string name
        string email UK "nullable"
    }
    USER_PREFERENCES {
        int id PK
        int user_id FK, UK
        json dietary_restrictions
        string default_effort_max
        text notes
    }
    GROCERY_LISTS {
        int id PK
        string name
        int meal_plan_id FK "nullable"
        int created_by_user_id FK "nullable"
    }
    GROCERY_LIST_ITEMS {
        int id PK
        int grocery_list_id FK
        int ingredient_id FK "nullable"
        string custom_text "nullable"
        bool is_checked
    }
```

## Environment variables

Mindless Meals reads exactly one database setting:

| Variable | Required | Example |
|---|---|---|
| `DATABASE_URL` | No -- falls back to SQLite | `postgresql://mindless_meals:changeme@postgres:5432/mindless_meals` |

See `mindless_meals/.env.example` and `postgres/.env.example`. In
production these are set via Doppler; locally, copy the `.env.example`
files to `.env` (gitignored).

## Local startup

```
cd mindless_meals/app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
FLASK_APP=app flask run --port=8000
```

Runs against SQLite with no further setup (this is unchanged from
before). To run against Postgres locally instead, see [Database
initialization](#database-initialization) and set `DATABASE_URL` before
starting Flask.

## Database initialization

Postgres is a **shared server** ("one database per application"), so
each application creates its own role and database rather than using the
server's superuser account. One-time setup for Mindless Meals:

```sql
CREATE ROLE mindless_meals WITH LOGIN PASSWORD '<pick a real password>';
CREATE DATABASE mindless_meals OWNER mindless_meals;
```

Run that as the Postgres superuser -- on Atlas, once the shared
`postgres` container is up:

```
docker exec -it postgres psql -U <POSTGRES_USER> -c \
  "CREATE ROLE mindless_meals WITH LOGIN PASSWORD '<password>';"
docker exec -it postgres psql -U <POSTGRES_USER> -c \
  "CREATE DATABASE mindless_meals OWNER mindless_meals;"
```

Then set `DATABASE_URL=postgresql://mindless_meals:<password>@postgres:5432/mindless_meals`
(via Doppler on Atlas, or `.env` locally) and run migrations (below) --
there is no separate "create the tables" step; Alembic does that.

## Migrations

Alembic is the authoritative schema history, living in
`mindless_meals/app/migrations/`. `db.create_all()` (used at app startup,
see `app.py`) still works for a quick local SQLite run, but Postgres
should always go through Alembic so schema changes are tracked,
reviewable, and reversible.

```
cd mindless_meals/app
source .venv/bin/activate           # after `pip install -r requirements.txt`
export DATABASE_URL=postgresql://mindless_meals:<password>@<host>:5432/mindless_meals

alembic upgrade head                # apply all migrations
alembic current                     # show the currently-applied revision
alembic history                     # list all revisions
alembic downgrade -1                # roll back one revision
alembic downgrade base              # roll back everything (drops all tables!)
```

`env.py` reads `DATABASE_URL` from the environment -- the same variable
the app itself uses -- and raises a clear error if it's unset, rather
than silently falling back to SQLite (a migration generated against the
wrong dialect could look fine and be subtly wrong).

### Current migration history

| Revision | Adds |
|---|---|
| `baseline schema` | `recipes`, `favorites`, `meal_plans`, `meal_plan_items` (the schema the app already ran on SQLite) |
| `add ingredient catalog and recipe ingredients` | `ingredients`, `recipe_ingredients` |
| `add unique constraint on recipe name and cuisine` | `UNIQUE(name, cuisine)` on `recipes` |
| `add users and user preferences` | `users`, `user_preferences` |
| `add grocery lists` | `grocery_lists`, `grocery_list_items` |

Each migration file's docstring has a rollback note for that specific
step (what `downgrade()` actually does and any risk in running it) --
read it before downgrading a database with real data in it.

### Generating a new migration

After changing `models.py`:

```
cd mindless_meals/app
export DATABASE_URL=postgresql://mindless_meals:<password>@<host>:5432/mindless_meals
alembic revision --autogenerate -m "describe the change"
```

Then **read the generated file** -- autogenerate is a good first draft,
not a guarantee (it won't detect every kind of change, e.g. some CHECK
constraint edits, and its downgrade() is often worth tightening by hand).
Verify with:

```
alembic upgrade head                            # apply it
alembic revision --autogenerate -m "drift check" # should generate an *empty* migration
```

An empty "drift check" migration means the DB now matches `models.py`
exactly. Delete that throwaway file once confirmed.

## Importing existing recipe data

The 48 seed recipes (and any recipe added later through the app) already
land in the database via the existing `seed.py` / Add Recipe flow --
`import-ingredients` is the additional step that builds the normalized
ingredient list from them:

```
cd mindless_meals/app
export DATABASE_URL=postgresql://mindless_meals:<password>@<host>:5432/mindless_meals
flask seed                  # existing command: loads seed_data/recipes.yaml (idempotent)
flask import-ingredients    # new command: builds ingredients/recipe_ingredients from Recipe rows
```

`import_ingredients.py`'s module docstring has the full methodology; in
short:

- Reads `Recipe.ingredients`/`.sauce` for every recipe already in the
  DB (not `recipes.yaml` directly) -- so it also picks up recipes a user
  adds or edits later through the app. **Nothing in `recipes.ingredients`
  or `.sauce` is ever modified.**
- **Idempotent and additive-only**: matches ingredients by name, matches
  links by `(recipe_id, ingredient_id)`, only ever inserts what's
  missing. Safe to re-run after adding/editing recipes. It does not
  reconcile removals -- editing a recipe to drop an ingredient leaves the
  old `recipe_ingredients` link in place (a possible staleness, not a
  data-loss risk).
- Matches ingredient text against the curated catalog in
  `seed_data/ingredients.yaml` (hand-classified `group`/`nutrition_type`
  for all 107 ingredients found in the 48 seed recipes). An ingredient
  not in that file yet (e.g. from a newly-added recipe) is still linked
  -- created unclassified (`group`/`nutrition_type` both `NULL`) rather
  than dropped -- and listed in the command's output so you can add a
  proper classification to `ingredients.yaml` and re-run.
- Two sauce values (`"—"` and `"Any sauce in fridge"`, used on a few
  "emergency meal" recipes to mean "whatever's around") are skipped as
  non-ingredient placeholders rather than becoming catalog entries. The
  original `sauce` text is untouched either way.
- A short, exhaustive, hand-reviewed list (`COMPOUND_MERGES` in
  `import_ingredients.py`) merges 8 "either works" source phrases (e.g.
  `"Ground turkey/beef"`, `"Chicken thighs or tofu"`) into one canonical
  ingredient each (e.g. `"Ground Meat (Any)"`), with the specific
  original items kept as `aliases`. This is the only ingredient text this
  importer rewrites/merges -- everything else is kept exactly as written.

Verified end-to-end against a real local Postgres 16 instance while
building this: `flask import-ingredients` on the 48 seed recipes produces
107 ingredients / 278 recipe-ingredient links with **zero** unmapped
tokens, and a second run creates 0 new rows (confirming idempotency).

## Backups

`postgres/scripts/backup.sh` -- plain-SQL `pg_dump` (via `docker exec` into
the running `postgres` container), gzip-compressed, timestamped:

```
postgres/scripts/backup.sh [database_name]     # default: mindless_meals
```

Writes to `postgres/backups/<database_name>_<UTC timestamp>.sql.gz`
(configurable via `BACKUP_DIR`) and deletes that database's backups older
than `RETENTION_DAYS` (default 14; set to `0` to disable). See the
script's header comment for a cron example. `postgres/backups/` is
gitignored -- backups are runtime data, not repo content.

Plain SQL (not `pg_dump`'s custom format) is deliberate: it can be
restored with nothing more than `psql`, and inspected/grepped with
`zcat` if you ever need to check what's actually in a backup.

On Atlas, backups land on local disk first (per the product requirements
for this project); off-site copies (e.g. synced to another machine or
cloud storage) are a deliberately separate, later step -- not implemented
here.

## Restoring a backup

`postgres/scripts/restore.sh`:

```
postgres/scripts/restore.sh <backup_file.sql.gz> [database_name]     # default: mindless_meals
```

The target database must already exist and be empty -- restoring into a
database with existing tables fails on the first conflicting object
rather than silently overwriting data. Create a fresh one first:

```
docker exec -it postgres psql -U <POSTGRES_USER> -c \
  "CREATE DATABASE mindless_meals_restored OWNER mindless_meals;"
postgres/scripts/restore.sh postgres/backups/mindless_meals_<timestamp>.sql.gz mindless_meals_restored
```

**Test a restore periodically**, not just when you need one for real:
restore into a throwaway database (as above), spot-check row counts and a
few real rows, then drop it:

```
docker exec -it postgres psql -U <POSTGRES_USER> -d mindless_meals_restored \
  -c "SELECT count(*) FROM recipes;" \
  -c "SELECT name, cuisine FROM recipes LIMIT 5;"
docker exec -it postgres psql -U <POSTGRES_USER> -c "DROP DATABASE mindless_meals_restored;"
```

(This exact backup → restore → row-count-comparison flow was run against
a real local Postgres 16 instance while building this feature, using the
full 48-recipe / 107-ingredient / 278-link dataset -- see the PR/commit
history for the verification output.)

## Verification steps

Everything below was actually run against a real local PostgreSQL 16
server (not just SQLite) while building this:

- `alembic upgrade head` from empty → all 5 migrations apply cleanly.
- `alembic downgrade base` → `alembic upgrade head` → clean round-trip,
  ends back at the same revision.
- `alembic revision --autogenerate` against a freshly-migrated database
  generates an **empty** migration -- confirms the hand-written migration
  files produce a schema that exactly matches `models.py` (no drift).
- `flask seed && flask import-ingredients` → 107 ingredients, 278
  recipe-ingredient links, 0 unmapped tokens; re-running creates 0 new
  rows (idempotency).
- Foreign key / constraint behavior (`ON DELETE CASCADE`, the
  `UNIQUE(recipe_id, ingredient_id)` pair, the `ingredients.group`
  `CHECK` constraint) exercised directly against Postgres.
- `pg_dump | gzip` → `gunzip | psql` into a fresh database → row counts
  for `recipes`/`ingredients`/`recipe_ingredients` match the source
  exactly.
- `docker compose config` (both `postgres/compose.yml` and
  `mindless_meals/compose.yml`, plus `postgres/compose.dev.yml`) resolves
  without error -- config/network/volume syntax validated, though actual
  container startup was **not** tested (no Docker daemon in this
  environment -- see [Known gaps](#known-gaps--deferred-work)).
- `pytest` (existing 30-test suite) still passes unchanged after the
  model additions.

## Atlas deployment

Not performed as part of this work -- this is what to do once you pull
this branch onto Atlas:

1. **Create the shared `atlas-data` network** (once, if it doesn't
   already exist alongside `atlas-proxy`):
   ```
   docker network create atlas-data
   ```
2. **Set up `postgres/.env`** (or the equivalent Doppler config) with
   real `POSTGRES_USER`/`POSTGRES_PASSWORD`, then bring the shared
   Postgres service up:
   ```
   cd ~/services/postgres
   docker compose up -d
   ```
3. **Create the Mindless Meals role/database** (see [Database
   initialization](#database-initialization) above).
4. **Run migrations** from a one-off container or a temporary local
   connection (see [Migrations](#migrations)) -- `alembic upgrade head`
   against the real `DATABASE_URL`.
5. **Run the recipe/ingredient import** (`flask seed` -- likely a no-op
   if recipes already exist from prior SQLite use; `flask
   import-ingredients`).
6. **Set `mindless_meals/.env`** (or Doppler) with the real
   `DATABASE_URL` pointing at the `postgres` service.
7. **Bring up Mindless Meals**:
   ```
   cd ~/services/mindless_meals
   docker compose up -d
   ```
   Bring `postgres` up first -- Compose can't express a health-based
   dependency across separate compose projects/directories, so
   `mindless_meals` will fail to connect (and retry, via its `restart:
   unless-stopped` policy) if it starts before Postgres is ready.
8. **Verify**: `curl http://localhost:8000/health`, then spot-check a
   few recipes in the UI, and confirm `docker exec postgres pg_dump ...`
   works before relying on it.
9. **Set up backup scheduling** (cron calling
   `postgres/scripts/backup.sh`) and, separately/later, off-site copies.
10. If you're moving existing *production* SQLite data (not just the
    seed recipes) onto Postgres, export it first with the app's own
    **Export Recipes** feature (`GET /api/recipes/export`) as a safety
    net, independent of this migration path.

## Known gaps / deferred work

Deliberately not done here -- flagged rather than silently skipped:

- **`ingredients`/`recipe_ingredients` aren't wired into `api.py` or the
  UI yet.** Add/Edit Recipe still only writes the free-text
  `ingredients`/`sauce` fields; nothing calls `import_ingredients()`
  automatically. Wiring that in (e.g. re-deriving a recipe's ingredient
  links whenever it's saved) is an application feature change, not
  database infrastructure, and was left out of this scope.
- **The new `UNIQUE(name, cuisine)` constraint on `recipes`** can now
  cause a raw database error on Create/Edit instead of the app's usual
  friendly `ValidationError`. Recommend a small follow-up in `api.py` to
  catch `IntegrityError` there and return a proper message.
- **No per-user favorites/meal plans/preferences wiring** -- `users`
  exists, but nothing else references a real `user_id` yet, since there's
  no authentication system to identify a "current user" with. Adding that
  is real feature work (and a real product decision about auth), not
  schema prep.
- **`grocery_lists`/`grocery_list_items` have no API or UI** yet --
  intentionally just the schema, ready for that feature.
- **Container startup was not tested** -- no Docker daemon in this
  development environment. `docker compose config` was used to validate
  syntax; the Postgres image/healthcheck/network/volume behavior itself
  should be smoke-tested once this reaches a Docker-capable machine
  (before or as part of the Atlas deploy above).
- **Off-site backup copies** are explicitly out of scope per the product
  requirements (local-on-Atlas first, off-site later, no paid cloud
  services).
