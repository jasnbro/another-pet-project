# Gym Log

A single-user home gym log, served from ATLAS at
**gym.undercurrentlabs.dev** (behind Cloudflare Access).

- **Plans, exercises and equipment are YAML files in `data/`.** Change them
  in git; the app picks them up on the next deploy. No code, no database
  migration.
- **Postgres stores only what you did:** sets, reps, weights, notes.
- Same stack as Mindless Meals: Flask, SQLAlchemy, Alembic, Postgres, uv,
  Docker Compose, deployed by `deploy/`.

Every change follows the same three steps: **edit the YAML → open a PR →
merge when CI is green.** Merging deploys it.

---

## Change my plan

The plan is `data/plans/home-gym-v1.yaml`.

- **Change sets or reps:** edit the numbers. `reps: [8, 12]` means 8 to 12.
  For timed holds (`hollow`) the numbers are seconds.
- **Swap an exercise:** change `key:` to another key from
  `data/exercises.yaml` (the Exercises page in the app lists them all).
- **Change which days are A or B:** edit `schedule:`. Weeks count from
  `starts:`; week 1 is `odd`.
- **Change how often deload weeks come:** `deload_every_weeks:`. In a
  deload week the app halves the sets.
- **Rename the plan:** change `name:` (e.g. `name: Fall 2026`). That's what
  the app shows. **Never change `plan:`**: it's the plan's permanent id,
  must match the file name, and every logged session stores it.

**Starting a whole new plan:** copy the file to
`data/plans/home-gym-v2.yaml`, change `plan:` to `home-gym-v2` (matching
the new file name), set `name:` and `starts:`, then set `active: false` in
the old file. Only one plan can be active. Old logs keep the plan they
were done under.

## Add an exercise

Add one line to `data/exercises.yaml`:

```yaml
step_up: { catalog: step-up, name: Step-up, what: "Step onto the bench holding dumbbells; drive through the front heel.", muscles: [quads, glutes], equipment: [powerblocks, flybird_bench], load: db_per_hand }
```

- The key (`step_up`) is permanent. Lowercase, underscores, never reused.
- `equipment:` uses keys from `data/equipment.yaml`; `[]` for bodyweight.
- `load:` is one of `db_single` (one dumbbell), `db_per_hand`,
  `bodyweight`, `seconds` (timed hold), `band`.
- Optional `alt: other_key`: shown instead whenever this exercise's
  equipment isn't all `owned` (like `bench` → `floor_press`).
- Optional `catalog: some-id`: links the exercise to a row in
  `data/catalog.csv` (302 exercises from Workout Guide, plus a few custom
  ones). Exercises with an illustration show it as a short loop on the
  Today card and the Exercises page. Find the id by searching the CSV for
  the exercise name. An exercise with no match can leave `catalog:` out, or
  get a custom row (see `catalog/README.md`).
- **Put quotes around text that has a comma**, or YAML splits it and CI
  fails: `name: "Single-arm row, lat-biased"`.

Then use it in the plan (see above).

**To stop using an exercise, never delete it.** Set `retired: true` and
take it out of the plan. Old logs still point at its key.

## Retire equipment (or mark it bought)

In `data/equipment.yaml`, change `status:`

- `planned` → `owned` when it arrives (e.g. `powerblocks` after pickup).
  Until then the app shows a "Needs …" note on those exercises and lists
  them under **Heads up** on the Plan page. It never blocks CI or the app.
- `owned` → `retired` when it leaves the house. Never delete the line.

Retiring something the active plan needs shows a warning (unless the
exercise has an `alt` that's fully owned). Swap those exercises in the plan,
or add an `alt`.

## Reading a CI failure

Open the failed **Gym Log** check on the PR, then the **Validate the YAML**
step. Each problem is one line naming the file. The common ones:

| The message says | What to do |
|---|---|
| `YAML doesn't parse` | A typo in the file: usually a missing `}` or quote, or a comma inside unquoted text. The message has the line number. |
| `unknown field (typo?)` | A misspelled field name, e.g. `rep:` instead of `reps:`. |
| `duplicate key 'x'` | The same key appears twice in one file. Rename or remove one. |
| `uses 'x', which isn't in exercises.yaml` | The plan names a key that doesn't exist. Check spelling against `exercises.yaml`. |
| `which is retired` | The plan (or an `alt`) uses a retired exercise. Pick another key. |
| `uses equipment 'x', which isn't in equipment.yaml` | Add the item to `equipment.yaml`, or fix the spelling. |
| `needs equipment that isn't owned` | Only ever a warning (it never fails CI). Mark it `owned` once you have it, or swap the exercise. |
| `more than one plan has active: true` / `no plan has active: true` | Exactly one plan file needs `active: true`. |
| `low ... is greater than high` / `sets must be at least 1` | Fix the numbers: `reps: [low, high]`, `sets` 1 or more. |
| `schedule.odd.mon is day 'C'` | The schedule names a day that isn't under `days:`. |
| `has catalog 'x', which isn't in catalog.csv` | The `catalog:` id is misspelled. Search `data/catalog.csv` for the exercise's name and copy its `id`. |
| `catalog.csv: missing column(s)` / `appears twice` | The CSV was hand-edited. Run `uv run python catalog/build_catalog.py` and commit the result. |
| `test_catalog_csv_is_up_to_date` failed | `catalog/build_catalog.py` changed but `data/catalog.csv` wasn't regenerated (or the CSV was hand-edited). Run the builder and commit. |
| `plan id '…' must match the file name` | `plan:` was changed. Put it back to the file's name and use `name:` for the plan's display name. |

The app runs the same check when it starts and won't start if it fails, so
a bad file can never go live.

---

## Using the app

- **Today:** picks Day A, Day B or rest from the plan, using the iPad's
  date. Tap Day A / Day B to override. Type weight and reps; it saves as
  you go ("Saved" at the top). The timer button on each set starts a 90 s
  rest (+30 s to extend); it chimes at zero even if the iPad locked in
  between. The speaker button mutes the chime on this device.
- **Last time** shows the previous session's sets. **Top of the range on
  every set** means go up a jump; otherwise same weight, beat last reps.
- **History** lists sessions; **Export CSV** downloads every set (opens in
  Excel or Numbers).
- **Install on the iPad:** open the site in Safari → Share → Add to Home
  Screen. It opens full screen.

## Run it locally

No database server needed (SQLite in `instance/`):

```
cd gym_log
uv sync
uv run flask --app app run --debug      # http://localhost:5000
uv run pytest                           # Python tests (incl. YAML validation)
node --test tests/*.test.js             # JavaScript tests
```

Against Postgres: set `DATABASE_URL` (see `.env.example`) and run
`uv run alembic upgrade head` first.

## Deploying (one-time setup on ATLAS)

Day to day, merging deploys. The first time only:

1. **Database.** On ATLAS, from a checkout of this repo:
   `postgres/scripts/create_app_database.sh gym_log`. It creates the
   `gym_log` database and the `gym_log_app` role, and prints the
   `DATABASE_URL` once.
2. **Service folder.** `mkdir -p ~/services/gym_log` and put that line in
   `~/services/gym_log/.env` (`chmod 600`).
3. **First deploy.** GitHub → Actions → **Gym Log** → Run workflow →
   `deploy`. The database is empty, so the deploy creates the tables.
4. **Tunnel.** Cloudflare Zero Trust → Networks → Tunnels → the ATLAS
   tunnel → Public hostname: `gym.undercurrentlabs.dev` → service
   `http://gym_log:8000`. (The tunnel config lives in Cloudflare, not in
   `cloudflared/compose.yml`.)
5. **Access.** Zero Trust → Access → Applications → Add a self-hosted app
   for `gym.undercurrentlabs.dev`, policy: allow your email. Do this
   **before** sharing the URL; the app has no login of its own.
6. **Backups.** `gym_log` is in the nightly encrypted backup to the SSD,
   followed by an automatic restore test (`postgres/README.md` → *Backups*).
   Every deploy also takes its own backup first.
7. **Test a restore** before relying on it: run the nightly cron command by
   hand and check it ends with `Restore test PASSED` for `gym_log`.

Rollback, logs and failures work exactly as for Mindless Meals:
see `deploy/README.md`.
