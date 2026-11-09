# Exercise catalog

`build_catalog.py` writes `../data/catalog.csv`: one row per exercise, 302
from Workout Guide 1.0.0 plus a few custom rows, each with training metadata.
An exercise in `data/exercises.yaml` links to a row with `catalog: <id>`.
The app uses the row's frames for the looping illustration.

Run it from `gym_log/` after changing anything here, and commit the CSV:

```
uv run python catalog/build_catalog.py
```

`tests/test_catalog.py` fails if the committed CSV doesn't match the builder.

## Sources (vendored, so the build is reproducible offline)

| Folder | What | License |
|---|---|---|
| `sources/workout-guide-1.0.0/` | `manifest.json` from `@bryllim/workout-guide@1.0.0` (npm) | Code MIT; frames and metadata CC BY-SA 4.0 (`LICENSE-ASSETS`, `ATTRIBUTION.md`) |
| `sources/exerciseapi-1.1.0/` | `data/exercises.json` from github.com/aschenoni/exercise-api, dataset 1.1.0 | CC BY 4.0 (`DATA-LICENSE`) |

The 906 frames themselves live in `../frames/`, copied unmodified from the
npm package, with its license files beside them. `../frames/README.md`
explains why they're outside `app/`.

## Where each row's metadata came from (`metadata_source`)

- `exerciseapi` (110 rows): substitution group, SFR, modality and rep range
  copied from ExerciseAPI, matched by `exerciseapi_id` (`EA_MAP`).
- `exerciseapi+override` (7 rows): same, but the substitution group was
  changed because ExerciseAPI's grouping breaks e1RM comparison. The reason
  is in `override_note` (`GROUP_OVERRIDES`).
- `claude` (185 rows): written by hand (`CLAUDE_ROWS`). Opinion, especially
  SFR; review before relying on it.
- `custom` (3 rows): exercises Gym Log uses that Workout Guide lacks
  (`dumbbell-floor-press`, `dumbbell-pullover`, `prone-band-leg-curl`). No
  illustration. Add more to `CUSTOM_ROWS`.

## Columns

- `frame_paths`: `|`-separated paths under `frames/`, in
  pose order (start, mid, end). Empty for custom rows.
- `preferred_rank`: computed, never copied. 1-based within
  `substitution_group`, ordered by SFR, then ExerciseAPI's curator rank where
  inherited, then loadable equipment first. Ties among hand-written rows
  fall back to name order, so rank within those is not meaningful.
- Only hypertrophy and calisthenics rows get `sfr_class` and
  `preferred_rank`; conditioning, mobility and prehab rows leave them empty.
- `rep_unit` is `seconds` for `duration` exercises (holds, stretches),
  `reps` otherwise. Cardio rows have no rep range.

The app reads only `id`, `name` and `frame_paths` today; the rest is there
for substitution and progress features later.

## Attribution (both required; shown at the bottom of the Exercises page)

- Exercise illustrations by Bryl Lim (https://bryllim.com), based on artwork
  by Everkinetic (https://github.com/everkinetic/data), licensed under
  CC BY-SA 4.0. Serve the frames unmodified: recolor with CSS masks only.
- Exercise data by ExerciseAPI (https://exercise-api.com), licensed under
  CC BY 4.0.
