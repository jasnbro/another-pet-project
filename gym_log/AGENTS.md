# Gym Log: notes for coding agents

Read the repo's root `AGENTS.md` first. Humans maintain this app by
editing YAML; keep it that way.

## File roles

| Path | Role |
|---|---|
| `data/exercises.yaml` | The key catalog. The only place an exercise key's meaning is defined. |
| `data/equipment.yaml` | What is owned (`owned` / `planned` / `retired`). |
| `data/plans/*.yaml` | Plans. Exactly one has `active: true`. |
| `data/catalog.csv` | Exercise catalog: illustration frames + training metadata. **Generated**; never hand-edit. |
| `catalog/` | `build_catalog.py` (writes `data/catalog.csv`), its vendored sources, and provenance/licenses. Not shipped in the image. |
| `frames/` | Workout Guide 1.0.0 frames (`<slug>/frame-1..3.png`), committed unmodified with their license; served at `/frames/`. Outside `app/` on purpose: the Dockerfile copies it in its own layer, before the code, so all kept images share one copy. Read `frames/README.md` before moving it. |
| `app/models.py` | Pydantic models for the YAML (`extra="forbid"`). |
| `app/loader.py` | Loads + cross-validates the YAML; same check in CI and at startup. |
| `app/schedule.py` | Plan week, A/B day, deload, progression cue. Pure functions. |
| `app/db.py` | The two Postgres tables (`gym_sessions`, `gym_sets`). |
| `app/api.py` | `/api/gym/*` routes. |
| `app/static/js/gym-log.js` | The front end (plain JS). Helpers in `logic.js`, Lucide icons in `icons.js`. |
| `migrations/` | Alembic. Postgres only; SQLite (dev/tests) uses `create_all()`. |

## Rules

- **Keys are permanent.** Never rename, reuse or delete an exercise or
  equipment key: logs store keys. Retire with `retired: true` /
  `status: retired`.
- **A plan's `plan:` id is permanent** and equals its file name (enforced).
  Sessions store it. The display name is `name:`.
- **Plans are never stored in Postgres.** A plan change must never need
  code or a migration. If it seems to, the design is wrong; ask.
- **Schedule uses plan weeks from `starts`, never ISO weeks.** "Today" is
  the client's local date, sent as `?date=`.
- New validation rules go in `loader.py` with a test in
  `tests/test_yaml_valid.py` (one per rule), and a row in the README's
  "Reading a CI failure" table.
- Schema changes: edit `app/db.py`, then
  `uv run alembic revision --autogenerate` against a real Postgres, and
  confirm `uv run alembic check` is clean afterwards.
- Icons: Lucide 0.468.0 only, stroke-width 1.5 (see `icons.js`). No emoji.
  The one exception is the Undercurrent octopus: the corner mark
  (`static/img/octopus-mark.png`, Mindless Meals' file, shown as a CSS
  mask) and the home-screen icons (Mindless Meals' icons recolored to
  this theme's `--accent` on `--bg`).
- **Exercise frames are CC BY-SA: never edit, recolor, crop or re-encode
  them.** They're white on transparent, so they're drawn as CSS masks in the
  theme's `--ink` (`.demo` in `gym-log.css`), the same way as the octopus
  mark. Keep the credit line on the Exercises page and the license files
  next to the frames.
- Catalog changes go in `catalog/build_catalog.py` (mappings, annotations,
  custom rows), then `uv run python catalog/build_catalog.py`; commit the
  regenerated `data/catalog.csv`. `tests/test_catalog.py` fails if they
  drift apart.
- Shared install snippet: edit `shared/undercurrent-web/`, then
  `shared/undercurrent-web/sync.sh gym_log`. Never edit the copies.

## Running checks

```
cd gym_log && uv sync
uv run pytest -q tests/test_yaml_valid.py   # just the YAML
uv run pytest -q                            # everything Python
node --test tests/*.test.js                 # JS helpers
```

Deploys: `APP=gym_log deploy/deploy.sh` via `.github/workflows/gym-log.yml`.
Never test against the production database (root `AGENTS.md`).
