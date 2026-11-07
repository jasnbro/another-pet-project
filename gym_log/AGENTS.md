# Gym Log: notes for coding agents

Read the repo's root `AGENTS.md` first. Humans maintain this app by
editing YAML; keep it that way.

## File roles

| Path | Role |
|---|---|
| `data/exercises.yaml` | The key catalog. The only place an exercise key's meaning is defined. |
| `data/equipment.yaml` | What is owned (`owned` / `planned` / `retired`). |
| `data/plans/*.yaml` | Plans. Exactly one has `active: true`. |
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
